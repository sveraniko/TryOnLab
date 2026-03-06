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
from app.providers.grok import GrokProvider
from app.providers.dummy import DummyProvider
from app.providers.openai import OpenAIProvider
from app.providers.registry import ProviderRegistry
from app.core.config import Settings
from app.services.storage import StorageBackend


def _allowlist(settings: Settings) -> set[str]:
    return {item.strip().lower() for item in settings.ai_provider_allowlist.split(',') if item.strip()}


def build_default_registry(storage: StorageBackend, settings: Settings) -> ProviderRegistry:
    registry = ProviderRegistry()
    allowed = _allowlist(settings)

    if 'dummy' in allowed:
        registry.register(DummyProvider(storage=storage))
    if settings.xai_api_key and 'grok' in allowed:
        registry.register(GrokProvider(storage=storage, settings=settings))
    if settings.openai_api_key and 'openai' in allowed:
        registry.register(OpenAIProvider(storage=storage, settings=settings))
    return registry


__all__ = [
    'DummyProvider',
    'GrokProvider',
    'OpenAIProvider',
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
