from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

from app.core.config import Settings
from app.services.storage import StorageBackend
from app.services.vision.composite import composite_patch_with_mask, mask_area_ratio
from app.services.vision.lock_engine import composite_crop_back, compute_scope_crop_rect
from app.services.vision.masks import build_scope_mask, dilate_mask, feather_mask, mask_bbox
from app.services.vision.parsing import build_parsing_backend

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LockEnginePlan:
    crop_rect: tuple[int, int, int, int]
    lock_engine: str
    parsing_backend: str
    mask: np.ndarray | None = None
    mask_area_ratio: float | None = None


async def prepare_controlled_patch(
    *,
    settings: Settings,
    storage: StorageBackend,
    job_id: str,
    base_image_bytes: bytes,
    scope: str,
) -> LockEnginePlan:
    base_img = Image.open(BytesIO(base_image_bytes)).convert('RGB')
    fallback_rect = compute_scope_crop_rect(base_img.width, base_img.height, scope)

    backend = build_parsing_backend(settings)
    if backend is None:
        return LockEnginePlan(crop_rect=fallback_rect, lock_engine='crop_v1_fallback', parsing_backend='none')

    try:
        parsing_result = await backend.parse_image(base_image_bytes)
        mask = build_scope_mask(parsing_result, scope)
        mask = dilate_mask(mask, settings.vision_mask_dilate_px)

        area = mask_area_ratio(mask)
        bbox = mask_bbox(mask, settings.vision_mask_margin_px)
        if bbox is None or area < 0.001:
            logger.warning('Mask area too small, fallback to crop_v1', extra={'job_id': job_id, 'scope': scope, 'area': area})
            return LockEnginePlan(crop_rect=fallback_rect, lock_engine='crop_v1_fallback', parsing_backend=backend.name)

        if settings.vision_debug_save_masks:
            await _save_debug_artifacts(storage, job_id, base_img, parsing_result.class_map, mask, bbox)

        return LockEnginePlan(
            crop_rect=bbox,
            lock_engine='mask_v1',
            parsing_backend=backend.name,
            mask=mask,
            mask_area_ratio=area,
        )
    except Exception:
        logger.exception('Parsing backend failed, fallback to crop_v1', extra={'job_id': job_id, 'scope': scope})
        return LockEnginePlan(crop_rect=fallback_rect, lock_engine='crop_v1_fallback', parsing_backend=backend.name)


async def compose_result(
    *,
    settings: Settings,
    base_image_bytes: bytes,
    edited_patch_bytes: bytes,
    plan: LockEnginePlan,
) -> bytes:
    if plan.lock_engine == 'mask_v1' and plan.mask is not None:
        x0, y0, x1, y1 = plan.crop_rect
        mask_crop = plan.mask[y0:y1, x0:x1]
        alpha = feather_mask(mask_crop, settings.vision_mask_feather_px)
        return composite_patch_with_mask(base_image_bytes, edited_patch_bytes, plan.crop_rect, alpha)

    return composite_crop_back(
        base_image_bytes,
        edited_patch_bytes,
        plan.crop_rect,
        feather_px=settings.vision_mask_feather_px,
    )


async def _save_debug_artifacts(
    storage: StorageBackend,
    job_id: str,
    base_image: Image.Image,
    class_map: np.ndarray,
    mask: np.ndarray,
    bbox: tuple[int, int, int, int],
) -> None:
    prefix = f'tryon/jobs/{job_id}/debug'

    class_norm = class_map.astype(np.float32)
    class_norm = (255 * (class_norm - class_norm.min()) / (class_norm.max() - class_norm.min() + 1e-6)).astype(np.uint8)
    class_img = Image.fromarray(class_norm, mode='L')
    raw_mask_img = Image.fromarray(mask, mode='L')
    feather_img = Image.fromarray(feather_mask(mask, 16), mode='L')

    x0, y0, x1, y1 = bbox
    crop_img = base_image.crop((x0, y0, x1, y1))

    for name, image in (
        ('parsing_class_preview.png', class_img),
        ('raw_mask.png', raw_mask_img),
        ('feathered_mask.png', feather_img),
        ('bbox_crop.png', crop_img),
    ):
        out = BytesIO()
        image.save(out, format='PNG')
        await storage.put_bytes(f'{prefix}/{name}', out.getvalue(), content_type='image/png')
