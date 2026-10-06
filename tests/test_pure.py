"""Tests for the pure functions - no database, no event loop."""

import pytest

from cache_service.service import interleave, payload_id


def test_interleave_takes_the_lists_in_turn():
    assert interleave(["a", "c"], ["b", "d"]) == ["a", "b", "c", "d"]


def test_interleave_rejects_mismatched_lengths():
    # strict=True in the zip: silently truncating would lose data, which is
    # worse than an error the caller can see.
    with pytest.raises(ValueError):
        interleave(["a"], ["b", "c"])


def test_identifier_is_stable_for_the_same_input():
    assert payload_id(["a"], ["b"]) == payload_id(["a"], ["b"])


def test_identifier_depends_on_order():
    # ["a"], ["b"] interleaves to "a, b" and ["b"], ["a"] to "b, a" - different
    # payloads, so they must not share an identifier.
    assert payload_id(["a"], ["b"]) != payload_id(["b"], ["a"])


def test_identifier_keeps_the_two_lists_apart():
    # Concatenating the lists before hashing would make these collide.
    assert payload_id(["a", "b"], ["c", "d"]) != payload_id(["a"], ["b"])
    assert payload_id(["ab"], ["c"]) != payload_id(["a"], ["bc"])
