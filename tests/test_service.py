"""Unit tests for the parts that make this a caching service."""

import pytest

from cache_service.service import get_or_create_payload, get_payload_output

pytestmark = pytest.mark.asyncio


async def test_creates_payload_and_renders_output(session, transformer):
    identifier, created = await get_or_create_payload(
        session, transformer, ["first string", "second"], ["other string", "another"]
    )

    assert created is True
    assert await get_payload_output(session, identifier) == (
        "FIRST STRING, OTHER STRING, SECOND, ANOTHER"
    )


async def test_duplicate_strings_are_transformed_once(session, transformer):
    # "repeat" appears three times across both lists; the transformer must be
    # asked about it exactly once.
    await get_or_create_payload(session, transformer, ["repeat", "repeat"], ["repeat", "unique"])

    assert transformer.calls == 1
    assert transformer.seen == [["repeat", "unique"]]


async def test_second_identical_request_does_no_work(session, transformer):
    first_id, first_created = await get_or_create_payload(session, transformer, ["a"], ["b"])
    second_id, second_created = await get_or_create_payload(session, transformer, ["a"], ["b"])

    assert first_id == second_id
    assert first_created is True
    assert second_created is False
    assert transformer.calls == 1  # no second call


async def test_overlapping_request_only_transforms_what_is_new(session, transformer):
    await get_or_create_payload(session, transformer, ["a"], ["b"])
    await get_or_create_payload(session, transformer, ["a"], ["c"])

    # Second request: "a" and "b" come from the database, only "c" is new.
    assert transformer.calls == 2
    assert transformer.seen == [["a", "b"], ["c"]]


async def test_unknown_identifier_returns_none(session):
    assert await get_payload_output(session, "does-not-exist") is None
