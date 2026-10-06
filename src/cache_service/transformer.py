"""The transformer function that stands in for an external service.

Two decisions here shape the whole service.

1. The interface takes a *batch* of strings and returns a batch. The task asks
   to minimise the number of calls, so the unit of work is "everything not
   already cached", not "one string". A per-string signature would make the
   call count equal to the number of cache misses instead of one.

2. It is a Protocol with a concrete implementation injected through FastAPI's
   dependency system, so tests substitute a counting fake and assert how often
   it was really called. Caching that is not measured is a claim, not a
   feature.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol


class Transformer(Protocol):
    async def __call__(self, values: Sequence[str]) -> list[str]:
        """Return the transformed strings, in the same order as the input."""
        ...


class UppercaseTransformer:
    """Upper-cases strings, slowly, and counts how often it was asked to.

    The sleep imitates the network round trip this would really be.
    """

    def __init__(self, latency_ms: int = 50) -> None:
        self._latency_s = latency_ms / 1000
        self.calls = 0

    async def __call__(self, values: Sequence[str]) -> list[str]:
        if not values:
            # Not calling the service at all is the cheapest call.
            return []
        self.calls += 1
        await asyncio.sleep(self._latency_s)
        return [value.upper() for value in values]
