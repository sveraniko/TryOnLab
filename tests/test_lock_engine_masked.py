from __future__ import annotations

from io import BytesIO

import pytest

np = pytest.importorskip("numpy", reason="numpy is required for mask engine tests")
from PIL import Image

from app.core.config import Settings
from app.services.storage import LocalStorageBackend
from app.services.vision.base import ParsingBackend, ParsingResult
from app.worker.lock_engine import compose_result, prepare_controlled_patch


class FakeParsingBackend(ParsingBackend):
    name = 'fake'

    def __init__(self, class_map: np.ndarray, labels: dict[str, int]) -> None:
        self._class_map = class_map
        self._labels = labels

    async def parse_image(self, image_bytes: bytes) -> ParsingResult:
        _ = image_bytes
        h, w = self._class_map.shape
        return ParsingResult(
            class_map=self._class_map,
            labels=self._labels,
            width=w,
            height=h,
            metadata={'fake': True},
        )


def _img_bytes(color: tuple[int, int, int], size: tuple[int, int] = (80, 80)) -> bytes:
    image = Image.new('RGB', size, color)
    out = BytesIO()
    image.save(out, format='JPEG')
    return out.getvalue()


@pytest.mark.asyncio
async def test_upper_scope_changes_only_upper_canvas(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class_map = np.zeros((80, 80), dtype=np.int32)
    class_map[5:45, 10:70] = 5
    class_map[45:75, 10:70] = 9
    labels = {'upper-clothes': 5, 'pants': 9, 'person': 1}
    backend = FakeParsingBackend(class_map, labels)
    monkeypatch.setattr('app.worker.lock_engine.build_parsing_backend', lambda settings: backend)

    settings = Settings(vision_mask_dilate_px=0, vision_mask_feather_px=0, vision_mask_margin_px=0)
    storage = LocalStorageBackend(str(tmp_path))
    base = _img_bytes((20, 20, 20))

    plan = await prepare_controlled_patch(
        settings=settings,
        storage=storage,
        job_id='job-upper',
        base_image_bytes=base,
        scope='upper',
    )
    result = await compose_result(
        settings=settings,
        base_image_bytes=base,
        edited_patch_bytes=_img_bytes((250, 0, 0), (plan.crop_rect[2] - plan.crop_rect[0], plan.crop_rect[3] - plan.crop_rect[1])),
        plan=plan,
    )

    image = Image.open(BytesIO(result)).convert('RGB')
    assert image.getpixel((30, 20))[0] > 180
    assert image.getpixel((30, 65))[0] < 80
    assert plan.lock_engine == 'mask_v1'


@pytest.mark.asyncio
async def test_lower_scope_does_not_touch_upper(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class_map = np.zeros((80, 80), dtype=np.int32)
    class_map[5:45, 10:70] = 5
    class_map[45:75, 10:70] = 9
    labels = {'upper-clothes': 5, 'pants': 9, 'person': 1}
    backend = FakeParsingBackend(class_map, labels)
    monkeypatch.setattr('app.worker.lock_engine.build_parsing_backend', lambda settings: backend)

    settings = Settings(vision_mask_dilate_px=0, vision_mask_feather_px=0, vision_mask_margin_px=0)
    storage = LocalStorageBackend(str(tmp_path))
    base = _img_bytes((20, 20, 20))

    plan = await prepare_controlled_patch(
        settings=settings,
        storage=storage,
        job_id='job-lower',
        base_image_bytes=base,
        scope='lower',
    )
    result = await compose_result(
        settings=settings,
        base_image_bytes=base,
        edited_patch_bytes=_img_bytes((0, 0, 250), (plan.crop_rect[2] - plan.crop_rect[0], plan.crop_rect[3] - plan.crop_rect[1])),
        plan=plan,
    )

    image = Image.open(BytesIO(result)).convert('RGB')
    assert image.getpixel((30, 20))[2] < 80
    assert image.getpixel((30, 65))[2] > 180
    assert plan.lock_engine == 'mask_v1'


@pytest.mark.asyncio
async def test_metadata_fallback_engine_when_mask_empty(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class_map = np.zeros((50, 50), dtype=np.int32)
    labels = {'background': 0}
    backend = FakeParsingBackend(class_map, labels)
    monkeypatch.setattr('app.worker.lock_engine.build_parsing_backend', lambda settings: backend)

    settings = Settings(vision_mask_dilate_px=0, vision_mask_feather_px=0, vision_mask_margin_px=0)
    storage = LocalStorageBackend(str(tmp_path))
    plan = await prepare_controlled_patch(
        settings=settings,
        storage=storage,
        job_id='job-fallback',
        base_image_bytes=_img_bytes((10, 10, 10), (50, 50)),
        scope='upper',
    )

    assert plan.lock_engine == 'crop_v1_fallback'
    assert plan.parsing_backend == 'fake'
