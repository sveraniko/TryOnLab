from pathlib import Path

import pytest

from app.providers.dummy import DummyProvider
from app.providers.registry import ProviderRegistry
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
