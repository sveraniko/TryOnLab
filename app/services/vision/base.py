from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ParsingResult:
    class_map: Any
    labels: dict[str, int]
    width: int
    height: int
    metadata: dict[str, object] = field(default_factory=dict)


class ParsingBackend(ABC):
    name: str = 'unknown'

    @abstractmethod
    async def parse_image(self, image_bytes: bytes) -> ParsingResult:
        raise NotImplementedError
