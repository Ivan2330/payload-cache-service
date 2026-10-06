"""cache-cli - a small client for testing the service programmatically.

Argument parsing is done by Pydantic Settings, as the task requires, so one
model both describes and validates the arguments: types are enforced,
"--repeat 0" is rejected before any request is sent, and --help is generated.

One deviation from the specification, deliberate and visible:

    the spec lists both  -h|--host  and  -h|--help

Those cannot coexist - argparse, which Pydantic Settings builds on, already
owns -h for help, and registering -h for host raises a conflict at import
time. The long option --host is exactly as specified; the short form is -s,
for "server", which is the word the spec itself uses to describe it.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from pydantic import AliasChoices, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CliArgs(BaseSettings):
    model_config = SettingsConfigDict(
        cli_parse_args=True,
        cli_prog_name="cache-cli",
        extra="forbid",
    )

    host: str = Field(
        "http://localhost:8000",
        validation_alias=AliasChoices("s", "host"),
        description="Base URL of the service (-h is reserved for --help)",
    )
    repeat: int = Field(
        1, ge=1, validation_alias=AliasChoices("r", "repeat"), description="Number of iterations"
    )
    input: str | None = Field(
        None,
        validation_alias=AliasChoices("i", "input"),
        description='Input file with the request JSON ("-" for stdin)',
    )
    json_arg: str | None = Field(
        None,
        validation_alias=AliasChoices("j", "json"),
        description="Request JSON given directly on the command line",
    )
    output: str = Field(
        "-",
        validation_alias=AliasChoices("o", "output"),
        description='Where to write the result ("-" for stdout)',
    )

    @model_validator(mode="after")
    def exactly_one_input(self) -> "CliArgs":
        if bool(self.input) == bool(self.json_arg):
            raise ValueError("Provide exactly one of --input or --json")
        return self


def read_request(args: CliArgs) -> dict:
    """Load the request body from whichever source was given."""
    raw = (
        args.json_arg
        if args.json_arg
        else (sys.stdin.read() if args.input == "-" else Path(args.input).read_text())
    )
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cache-cli: input is not valid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise SystemExit("cache-cli: input JSON must be an object with list_1 and list_2")
    return body


def write_output(args: CliArgs, text: str) -> None:
    if args.output == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(args.output).write_text(text + "\n")


async def run(args: CliArgs) -> int:
    body = read_request(args)
    results = []

    async with httpx.AsyncClient(base_url=args.host, timeout=30.0) as client:
        for iteration in range(1, args.repeat + 1):
            started = time.perf_counter()

            created = await client.post("/payload", json=body)
            if created.status_code >= 400:
                raise SystemExit(
                    f"cache-cli: POST /payload failed with {created.status_code}: {created.text}"
                )
            payload_id = created.json()["id"]

            fetched = await client.get(f"/payload/{payload_id}")
            if fetched.status_code >= 400:
                raise SystemExit(
                    f"cache-cli: GET /payload failed with {fetched.status_code}: {fetched.text}"
                )

            results.append(
                {
                    "iteration": iteration,
                    "id": payload_id,
                    "reused": not created.json()["created"],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                    "output": fetched.json()["output"],
                }
            )

    # Timings are part of the output on purpose: with --repeat they make the
    # effect of the cache visible instead of merely asserted.
    write_output(args, json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def _long_option(location: tuple) -> str:
    """Map a Pydantic error location back to the option the user actually typed."""
    if not location:
        return ""
    key = str(location[0])
    for name, field in CliArgs.model_fields.items():
        alias = field.validation_alias
        choices = [str(c) for c in alias.choices] if isinstance(alias, AliasChoices) else [name]
        if key in choices:
            return "--" + max(choices, key=len)
    return key


def main() -> int:
    """Entry point. Argument and transport failures are reported, not raised.

    A command line tool that answers a typo with a traceback is a tool nobody
    wants to use, so each failure gets a message and a conventional exit code:
    2 for bad arguments, 1 for everything else.
    """
    try:
        args = CliArgs()
    except ValidationError as exc:
        for error in exc.errors():
            option = _long_option(error["loc"])
            message = error["msg"].removeprefix("Value error, ")
            prefix = f"{option}: " if option else ""
            print(f"cache-cli: {prefix}{message}", file=sys.stderr)
        print("Try 'cache-cli --help' for the available options.", file=sys.stderr)
        return 2

    try:
        return asyncio.run(run(args))
    except httpx.HTTPError as exc:
        print(f"cache-cli: cannot reach {args.host} ({type(exc).__name__})", file=sys.stderr)
        return 1
    except OSError as exc:
        detail = f"{exc.strerror}: {exc.filename}" if exc.filename else str(exc)
        print(f"cache-cli: {detail}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
