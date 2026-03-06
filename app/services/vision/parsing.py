from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from app.services.vision.base import ParsingBackend, ParsingResult

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency in tests
    cv2 = None

try:
    import onnxruntime as ort
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency in tests
    ort = None

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class NoopParsingBackend(ParsingBackend):
    name = 'none'

    async def parse_image(self, image_bytes: bytes) -> ParsingResult:
        _ = image_bytes
        raise RuntimeError('Parsing backend disabled')


class OnnxHumanParsingBackend(ParsingBackend):
    name = 'onnx'

    def __init__(self, model_path: str) -> None:
        if ort is None or cv2 is None:
            raise RuntimeError('onnxruntime and opencv-python-headless are required for ONNX parsing backend')
        self.model_path = model_path
        self._session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        inputs = self._session.get_inputs()
        if not inputs:
            raise RuntimeError('ONNX parsing model has no inputs')
        self._input_name = inputs[0].name

    async def parse_image(self, image_bytes: bytes) -> ParsingResult:
        return await asyncio.to_thread(self._parse_sync, image_bytes)

    def _parse_sync(self, image_bytes: bytes) -> ParsingResult:
        image = Image.open(BytesIO(image_bytes)).convert('RGB')
        width, height = image.size
        np_image = np.array(image)

        tensor = self._preprocess(np_image)
        outputs = self._session.run(None, {self._input_name: tensor})
        class_map = self._postprocess(outputs[0], width, height)

        labels = {
            'background': 0,
            'person': 1,
            'upper-clothes': 5,
            'pants': 9,
            'skirt': 12,
            'dress': 6,
            'left-shoe': 18,
            'right-shoe': 19,
        }
        metadata: dict[str, object] = {'backend': 'onnx', 'model_path': self.model_path}
        return ParsingResult(class_map=class_map, labels=labels, width=width, height=height, metadata=metadata)

    def _preprocess(self, np_image: np.ndarray) -> np.ndarray:
        input_meta = self._session.get_inputs()[0]
        _, _, target_h, target_w = input_meta.shape
        if not isinstance(target_h, int) or not isinstance(target_w, int):
            target_h, target_w = 512, 512

        resized = cv2.resize(np_image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        normalized = resized.astype(np.float32) / 255.0
        normalized = (normalized - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
            [0.229, 0.224, 0.225], dtype=np.float32
        )
        chw = normalized.transpose(2, 0, 1)
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _postprocess(self, output: np.ndarray, width: int, height: int) -> np.ndarray:
        logits = output
        if logits.ndim == 4:
            logits = logits[0]
        class_map = np.argmax(logits, axis=0).astype(np.int32)
        resized = cv2.resize(class_map, (width, height), interpolation=cv2.INTER_NEAREST)
        return resized.astype(np.int32)


def build_parsing_backend(settings: 'Settings') -> ParsingBackend | None:
    backend = settings.vision_parsing_backend.strip().lower()
    if backend == 'onnx':
        model_path = Path(settings.vision_parsing_model_path)
        if not model_path.exists():
            logger.warning('Parsing model path not found, falling back to crop_v1', extra={'model_path': str(model_path)})
            return None
        try:
            return OnnxHumanParsingBackend(str(model_path))
        except Exception:
            logger.exception('Failed to initialize ONNX parsing backend, falling back to crop_v1')
            return None

    return None
