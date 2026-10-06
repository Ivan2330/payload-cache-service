"""Shared dependencies.

The transformer is one long-lived object rather than one per request: it
stands in for a service client, and clients hold connections. Keeping it in
one module also gives the tests a single place to override.
"""

from cache_service.config import settings
from cache_service.transformer import Transformer, UppercaseTransformer

_transformer: Transformer = UppercaseTransformer(settings.transformer_latency_ms)


def get_transformer() -> Transformer:
    return _transformer
