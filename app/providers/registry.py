from __future__ import annotations

from app.providers.base import ProviderBase


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderBase] = {}

    def register(self, provider: ProviderBase) -> None:
        key = provider.name.strip().lower()
        if not key:
            raise ValueError('Provider name cannot be empty')
        self._providers[key] = provider

    def get(self, name: str) -> ProviderBase:
        key = name.strip().lower()
        if key not in self._providers:
            raise KeyError(f'Provider not registered: {name}')
        return self._providers[key]

    def list(self) -> list[str]:
        return sorted(self._providers.keys())
