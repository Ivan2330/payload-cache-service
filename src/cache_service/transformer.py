"""Stands in for an external service.

Batch in, batch out: the unit of work is everything not already cached, so a
request costs one call rather than one per cache miss.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol


class Transformer(Protocol):
    async def __call__(self, values: Sequence[str]) -> list[str]:
        """Return the transformed strings, in the same order as the input."""
        ...


class UppercaseTransformer:
    """Upper-cases strings, with a sleep standing in for a network round trip."""

    def __init__(self, latency_ms: int = 50) -> None:
        self._latency_s = latency_ms / 1000
        self.calls = 0

    async def __call__(self, values: Sequence[str]) -> list[str]:
        if not values:
            return []
        self.calls += 1
        await asyncio.sleep(self._latency_s)
        return [value.upper() for value in values]
