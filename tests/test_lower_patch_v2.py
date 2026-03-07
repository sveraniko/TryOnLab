from __future__ import annotations

from io import BytesIO

import pytest

np = pytest.importorskip('numpy', reason='numpy is required for lower patch tests')
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
        return ParsingResult(class_map=self._class_map, labels=self._labels, width=w, height=h, metadata={})


def _img_bytes(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    image = Image.new('RGB', size, color)
    out = BytesIO()
    image.save(out, format='JPEG')
    return out.getvalue()


@pytest.mark.asyncio
async def test_lower_bbox_expands_up_and_sets_v2_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class_map = np.zeros((100, 100), dtype=np.int32)
    class_map[50:90, 20:80] = 9
    labels = {'pants': 9, 'person': 1}
    backend = FakeParsingBackend(class_map, labels)
    monkeypatch.setattr('app.worker.lock_engine.build_parsing_backend', lambda settings: backend)

    settings = Settings(
        vision_mask_margin_px=0,
        lower_waist_overlap_px=12,
        lower_min_top_extension_ratio=0.0,
        lower_mask_dilate_up_px=0,
        lower_mask_dilate_side_px=0,
        lower_mask_dilate_down_px=0,
    )
    plan = await prepare_controlled_patch(
        settings=settings,
        storage=LocalStorageBackend(str(tmp_path)),
        job_id='job-lower-v2',
        base_image_bytes=_img_bytes((10, 10, 10)),
        scope='lower',
    )

    assert plan.lock_engine == 'mask_v1_lower_v2'
    assert plan.crop_rect[1] <= 38
    assert plan.metadata['lower_patch_v2'] is True
    assert plan.metadata['composite_mode'] == 'core+edge'


@pytest.mark.asyncio
async def test_lower_core_edge_masks_and_composite(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class_map = np.zeros((100, 100), dtype=np.int32)
    class_map[45:95, 20:80] = 9
    labels = {'pants': 9, 'person': 1}
    backend = FakeParsingBackend(class_map, labels)
    monkeypatch.setattr('app.worker.lock_engine.build_parsing_backend', lambda settings: backend)

    settings = Settings(
        vision_mask_margin_px=0,
        lower_waist_overlap_px=10,
        lower_min_top_extension_ratio=0.0,
        lower_core_erode_px=6,
        lower_edge_feather_px=6,
        lower_mask_dilate_up_px=4,
        lower_mask_dilate_side_px=0,
        lower_mask_dilate_down_px=0,
    )
    plan = await prepare_controlled_patch(
        settings=settings,
        storage=LocalStorageBackend(str(tmp_path)),
        job_id='job-lower-v2-composite',
        base_image_bytes=_img_bytes((25, 25, 25)),
        scope='lower',
    )

    assert plan.core_mask is not None
    assert plan.edge_mask is not None
    assert plan.lock_engine.endswith('lower_v2')

    patch_w = plan.crop_rect[2] - plan.crop_rect[0]
    patch_h = plan.crop_rect[3] - plan.crop_rect[1]
    result = await compose_result(
        settings=settings,
        base_image_bytes=_img_bytes((25, 25, 25)),
        edited_patch_bytes=_img_bytes((220, 0, 0), (patch_w, patch_h)),
        plan=plan,
    )

    image = Image.open(BytesIO(result)).convert('RGB')
    waist_pixel = image.getpixel((50, max(46, plan.crop_rect[1] + 8)))
    assert waist_pixel[0] > 120
