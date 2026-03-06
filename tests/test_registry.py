from pathlib import Path
import importlib.util

import pytest

from app.providers.dummy import DummyProvider
from app.providers import build_default_registry
from app.providers.registry import ProviderRegistry
from app.core.config import Settings
from app.services.storage import LocalStorageBackend


def test_registry_register_and_get(tmp_path: Path) -> None:
    registry = ProviderRegistry()
    provider = DummyProvider(storage=LocalStorageBackend(root_dir=str(tmp_path)))
    registry.register(provider)

    loaded = registry.get('dummy')
    assert loaded is provider
    assert registry.list() == ['dummy']


def test_registry_get_missing_raises_key_error() -> None:
    registry = ProviderRegistry()
    with pytest.raises(KeyError):
        registry.get('missing')


def test_default_registry_has_only_dummy_without_keys(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))
    settings = Settings(
        xai_api_key='',
        openai_api_key='',
        ai_provider_allowlist='grok,openai,dummy',
    )

    registry = build_default_registry(storage, settings)
    assert registry.list() == ['dummy']


def test_default_registry_registers_real_providers_when_keys_exist(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=str(tmp_path))
    settings = Settings(
        xai_api_key='xai-key',
        openai_api_key='openai-key',
        ai_provider_allowlist='grok,openai,dummy',
    )

    registry = build_default_registry(storage, settings)
    if importlib.util.find_spec('httpx') is None:
        assert registry.list() == ['dummy']
    else:
        assert registry.list() == ['dummy', 'grok', 'openai']
