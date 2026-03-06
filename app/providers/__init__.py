from app.providers.base import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderBase,
    ProviderCapabilities,
    ProviderError,
    ProviderRateLimitError,
    ProviderResult,
    ProviderTemporaryError,
    ProviderUnsupportedError,
)
from app.providers.dummy import DummyProvider
from app.providers.registry import ProviderRegistry
from app.services.storage import StorageBackend


def build_default_registry(storage: StorageBackend) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(DummyProvider(storage=storage))
    return registry


__all__ = [
    'DummyProvider',
    'ProviderAuthError',
    'ProviderBadRequestError',
    'ProviderBase',
    'ProviderCapabilities',
    'ProviderError',
    'ProviderRateLimitError',
    'ProviderRegistry',
    'ProviderResult',
    'ProviderTemporaryError',
    'ProviderUnsupportedError',
    'build_default_registry',
]
