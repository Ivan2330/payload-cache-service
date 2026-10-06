# Caching Service

A FastAPI microservice that builds a payload from two lists of strings and
caches the expensive part of that work, so it is never done twice.

```
POST /payload   {"list_1": [...], "list_2": [...]}   ->  {"id": "...", "created": true}
GET  /payload/{id}                                   ->  {"output": "..."}
```

The payload is the interleaving of the two lists after each string has passed
through a "transformer function" that stands in for an external service.

### A worked example

```
POST /payload
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}

201  {"id": "831db673...1da401", "created": true, "message": "Payload created"}
```

```
GET /payload/831db673...1da401

200  {"output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

Sending that same `POST` a second time returns the same identifier with
`"created": false`, and the transformer is not called at all.

---

## Running it

**Docker** - the whole service, no local Python:

```bash
docker compose up --build
curl -X POST localhost:8000/payload \
  -H 'content-type: application/json' \
  -d '{"list_1":["first string","second string"],"list_2":["other string","another string"]}'
```

**Locally** - Python 3.12 or newer:

```bash
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn cache_service.main:app --reload
pytest
```

Interactive API documentation is at `http://localhost:8000/docs`.

Both settings can be overridden by environment variable or a `.env` file;
`.env.example` lists them with their defaults.

**PostgreSQL instead of SQLite** - one variable, because every query is plain
SQLAlchemy:

```bash
docker compose --profile postgres up -d postgres
CACHE_DATABASE_URL=postgresql+asyncpg://cache:cache@localhost:5432/cache \
  uvicorn cache_service.main:app
```

To run both in containers, address the database by its service name instead.
No host port is involved, so this also works on a machine that already has
PostgreSQL listening on 5432:

```bash
docker compose --profile postgres up -d postgres
CACHE_DATABASE_URL=postgresql+asyncpg://cache:cache@postgres:5432/cache \
  docker compose --profile postgres up -d --build api
```

Either way the tables are created on startup, and the only code that changes
between the two databases is the conflict-aware insert in `service.py`.

## The CLI

```bash
cache-cli --host http://localhost:8000 --repeat 5 --json '{"list_1":["a"],"list_2":["b"]}'
cache-cli --input request.json --output result.json
echo '{"list_1":["a"],"list_2":["b"]}' | cache-cli --input -
```

Each iteration reports the identifier, whether the payload was reused, the
round trip time and the output. Timings are included on purpose: with
`--repeat` they make the effect of the cache visible rather than asserted.

Failures are reported rather than raised - bad arguments exit 2, anything else
exits 1, and no path prints a traceback.

---

## What the cache actually saves

The task asks to minimise the *number of calls* to the transformer, so that is
what is measured rather than asserted. Every row below comes out of the test
suite:

| Scenario | Strings in | Calls | Batches sent |
| --- | --- | --- | --- |
| one request, six distinct strings | 6 | 1 | `[a d b e c f]` |
| one request, the same string four times | 4 | 1 | `[x]` |
| the same request sent twice | 4 | 1 | `[a b]` |
| second request shares one string with the first | 4 | 2 | `[a b]`, `[c]` |
| second request fully covered by the cache | 6 | 1 | `[a c b d]` |

Two things to read off that table. The call count follows the number of
*distinct uncached* strings rather than the size of the request - six strings
cost one call, and a request the cache already covers costs none. And in the
overlapping row the second batch is `[c]` alone: the two strings already
stored were not sent again.

End to end, over an ASGI transport, with the transformer's simulated latency
at its default 50 ms:

```
POST #1   201    75.9 ms   created: true
POST #2   201     3.1 ms   created: false      <- no transformer call
GET       200     3.1 ms   output: FIRST STRING, OTHER STRING, ...
```

## Tests

```
pytest             16 passed
ruff check .       All checks passed
```

* `test_pure.py` - interleaving and identifier, no I/O. Covers order
  sensitivity and the collision that concatenating the lists before hashing
  would cause: `["ab"], ["c"]` against `["a"], ["bc"]`.
* `test_service.py` - caching against a real database, asserting the call
  count and the contents of each batch. These are the tests that fail if the
  cache quietly stops working while the output stays correct.
* `test_api.py` - the endpoints end to end: status codes, the `created` flag,
  422 on mismatched and on empty lists, 404 on an unknown identifier.

---

## Decisions, and why

**The identifier is a hash of the request, not a random id.**
`payload_id` is the SHA-256 of the canonical JSON of both lists. Two identical
requests therefore produce the same identifier with no lookup table, and two
concurrent identical requests cannot race each other into creating two
identifiers for the same payload. The lists are hashed in the order they
arrive and as two separate keys - `["a"], ["b"]` is a different payload from
`["b"], ["a"]`, and `["ab"], ["c"]` must not collide with `["a"], ["bc"]`.

**The transformer takes a batch.**
The task asks to minimise the *number of calls*, so the unit of work is
"everything not already cached", not "one string". A request is served with at
most one call, and a request whose strings are all cached makes none. Three
things get the count down, in this order: duplicates inside the request
collapse first, everything already stored is fetched in a single
`SELECT ... IN`, and only the remainder is sent.

**Two caches, because there are two different expensive things.**
`transformed_strings` holds one row per distinct source string - that is the
external call being avoided. `payloads` holds the assembled output - that is
the assembly being avoided. The second table makes `GET` a single primary-key
read that does not depend on the first table still holding every entry.

Storing the rendered output duplicates data that could be recomputed from the
cache. That is deliberate: the read path is the hot one and should not re-join
and re-render on every request. The cost is that changing the output format
would need a backfill.

**Writes use `ON CONFLICT DO NOTHING` rather than catching `IntegrityError`.**
Two requests may transform the same new string at the same moment, and that is
normal rather than exceptional. In PostgreSQL a failed statement also aborts
the whole transaction, so catching the error would mean a rollback and a retry
where a conflict clause means neither.

**Both SQLite and PostgreSQL are supported.**
SQLite is the default so the service runs with no infrastructure and the tests
need none. The two dialects differ in exactly one place - the conflict-aware
insert in `service.py` - and the engine URL. Nothing else in the code knows
which database is in use.

**`POST` answers 201 both times, with a `created` flag.**
A repeated request is the same resource rather than a conflict, so 409 would
be wrong, and the client should not have to care which of its requests arrived
first. The flag says which happened, and the CLI surfaces it.

**The transformer is injected, not imported.**
It is a `Protocol` resolved through FastAPI's dependency system, so the tests
substitute a counting fake and assert how many times it was really called.
Caching that is not measured is a claim, not a feature - the tests check the
call count, not just the output.

**Validation lives in the Pydantic models.**
Mismatched or empty lists are rejected with 422 before any business logic
runs, and the rule appears in the generated OpenAPI document.

---

## One deviation from the specification

The CLI section of the task lists both:

```
[-h|--host URL]  ...  [-h|--help]
```

These cannot both exist. Pydantic Settings builds its parser on `argparse`,
which already owns `-h` for help; registering `-h` for the host raises a
conflict at import time. `--host` is kept exactly as specified and `-s` is the
short form, for "server" - the word the task itself uses to describe it. `-h`
remains help.

Flagging it seemed better than silently choosing; if the intent was the
opposite - host on `-h`, help only on `--help` - it is a one-line change.

---

## Shortcuts taken, and what production would need

* **Schema creation uses `create_all`,** not migrations. For a service that
  owns its schema over time, this would be Alembic.
* **The cache never expires.** The transformation here is pure, so a cached
  result cannot go stale. A real external service would need a TTL or an
  invalidation signal - a column and a predicate, not a redesign.
* **No authentication, rate limiting or request size cap.** All three belong
  at the edge of a real deployment.
* **The transformer runs in-process.** It stands in for a network call; a real
  client would need timeouts, retries with backoff and a circuit breaker.

---

## Layout

```
src/cache_service/
  main.py          application setup and lifespan
  api.py           routes, status codes
  schemas.py       request and response models, validation
  service.py       identity, caching and assembly - no FastAPI imports
  transformer.py   the simulated external service, behind a Protocol
  models.py        tables
  db.py            engine, session factory, schema creation
  config.py        settings
  dependencies.py  shared dependency wiring
  cli.py           cache-cli, argument parsing via Pydantic Settings
tests/
  test_pure.py     interleaving and identifier, no I/O
  test_service.py  caching behaviour against a real database
  test_api.py      the endpoints end to end
```

`service.py` imports nothing from FastAPI. The business rules are testable
without an HTTP layer in the way, and the HTTP layer stays thin enough to read
in one sitting.
