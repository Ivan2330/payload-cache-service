"""Business logic: identity of a payload, caching, and assembly.

No FastAPI imports here on purpose: these functions take a session and a
transformer, nothing else.
"""

import hashlib
import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache_service.models import Payload, TransformedString
from cache_service.transformer import Transformer

SEPARATOR = ", "


def interleave(list_1: Sequence[str], list_2: Sequence[str]) -> list[str]:
    """Take the lists in turn: first of one, first of the other, and so on."""
    result: list[str] = []
    for left, right in zip(list_1, list_2, strict=True):
        result.append(left)
        result.append(right)
    return result


def payload_id(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Identify a request by its content, which makes a repeat free to detect.

    Order matters, and the two lists are hashed as separate keys so that
    ["ab"], ["c"] cannot collide with ["a"], ["bc"].
    """
    canonical = json.dumps(
        {"list_1": list(list_1), "list_2": list(list_2)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unique_in_order(values: Sequence[str]) -> list[str]:
    """Distinct values, first-seen order kept so results stay reproducible."""
    return list(dict.fromkeys(values))


async def _insert_ignoring_conflicts(session: AsyncSession, table, rows: list[dict]) -> None:
    """Insert rows, skipping ones another request inserted first.

    Two requests can legitimately be transforming the same string at the same
    moment. ON CONFLICT DO NOTHING beats catching IntegrityError: in PostgreSQL
    a failed statement aborts the whole transaction and forces a rollback.
    """
    if not rows:
        return

    dialect = session.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - only two dialects are supported by design
        raise RuntimeError(f"Unsupported database dialect: {dialect}")

    await session.execute(insert(table).values(rows).on_conflict_do_nothing())


async def _transform_with_cache(
    session: AsyncSession, transformer: Transformer, values: Sequence[str]
) -> dict[str, str]:
    """Map every input string to its transformed form, calling out at most once.

    Duplicates collapse first, cached values come back in one SELECT, and only
    the remainder is sent.
    """
    wanted = _unique_in_order(values)
    if not wanted:
        return {}

    rows = await session.execute(
        select(TransformedString).where(TransformedString.source.in_(wanted))
    )
    mapping = {row.source: row.transformed for row in rows.scalars()}

    missing = [value for value in wanted if value not in mapping]
    if missing:
        transformed = await transformer(missing)
        if len(transformed) != len(missing):
            raise ValueError("Transformer returned a different number of values")
        mapping.update(zip(missing, transformed, strict=True))
        await _insert_ignoring_conflicts(
            session,
            TransformedString,
            [
                {"source": source, "transformed": value}
                for source, value in zip(missing, transformed, strict=True)
            ],
        )

    return mapping


async def get_or_create_payload(
    session: AsyncSession,
    transformer: Transformer,
    list_1: Sequence[str],
    list_2: Sequence[str],
) -> tuple[str, bool]:
    """Return the payload identifier and whether this call created it."""
    identifier = payload_id(list_1, list_2)

    if await session.get(Payload, identifier) is not None:
        # Already built: no transformer call, no write, no second identifier.
        return identifier, False

    ordered = interleave(list_1, list_2)
    mapping = await _transform_with_cache(session, transformer, ordered)
    output = SEPARATOR.join(mapping[value] for value in ordered)

    await _insert_ignoring_conflicts(session, Payload, [{"id": identifier, "output": output}])
    await session.commit()
    return identifier, True


async def get_payload_output(session: AsyncSession, identifier: str) -> str | None:
    """Read a stored payload, or None if that identifier is unknown."""
    payload = await session.get(Payload, identifier)
    return payload.output if payload else None
