from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.storage import StorageBackend

try:
    from app.providers.grok import GrokProvider
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight test env
    GrokProvider = None  # type: ignore[assignment]

try:
    from app.providers.openai import OpenAIProvider
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight test env
    OpenAIProvider = None  # type: ignore[assignment]


def _allowlist(settings: 'Settings') -> set[str]:
    return {item.strip().lower() for item in settings.ai_provider_allowlist.split(',') if item.strip()}


def build_default_registry(storage: 'StorageBackend', settings: 'Settings') -> ProviderRegistry:
    registry = ProviderRegistry()
    allowed = _allowlist(settings)

    if 'dummy' in allowed:
        registry.register(DummyProvider(storage=storage))
    if GrokProvider is not None and settings.xai_api_key and 'grok' in allowed:
        registry.register(GrokProvider(storage=storage, settings=settings))
    if OpenAIProvider is not None and settings.openai_api_key and 'openai' in allowed:
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
