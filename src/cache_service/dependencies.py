"""Shared dependencies."""

from cache_service.config import settings
from cache_service.transformer import Transformer, UppercaseTransformer

# One instance, not one per request: it stands in for a client holding connections.
_transformer: Transformer = UppercaseTransformer(settings.transformer_latency_ms)


def get_transformer() -> Transformer:
    return _transformer
