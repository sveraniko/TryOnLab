from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from app.core.config import Settings
from app.services.storage import StorageBackend
from app.services.vision.composite import composite_patch_with_core_edge, composite_patch_with_mask, mask_area_ratio
from app.services.vision.lock_engine import composite_crop_back, compute_scope_crop_rect
from app.services.vision.masks import (
    build_scope_mask,
    dilate_mask,
    dilate_mask_asymmetric,
    erode_mask,
    feather_mask,
    mask_bbox,
)
from app.services.vision.parsing import build_parsing_backend

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LockEnginePlan:
    crop_rect: tuple[int, int, int, int]
    lock_engine: str
    parsing_backend: str
    mask: np.ndarray | None = None
    core_mask: np.ndarray | None = None
    edge_mask: np.ndarray | None = None
    mask_area_ratio: float | None = None
    composite_mode: str = 'feather'
    metadata: dict[str, object] = field(default_factory=dict)


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
        engine = 'crop_v1_lower_v2_fallback' if scope == 'lower' else 'crop_v1_fallback'
        return LockEnginePlan(crop_rect=_expand_fallback_rect(settings, fallback_rect, base_img.height, scope), lock_engine=engine, parsing_backend='none')

    try:
        parsing_result = await backend.parse_image(base_image_bytes)
        mask_raw = build_scope_mask(parsing_result, scope)
        mask = _build_target_mask(settings, mask_raw, scope)

        area = mask_area_ratio(mask)
        bbox = mask_bbox(mask, settings.vision_mask_margin_px)
        if bbox is None or area < 0.001:
            logger.warning('Mask area too small, fallback to crop_v1', extra={'job_id': job_id, 'scope': scope, 'area': area})
            engine = 'crop_v1_lower_v2_fallback' if scope == 'lower' else 'crop_v1_fallback'
            return LockEnginePlan(crop_rect=_expand_fallback_rect(settings, fallback_rect, base_img.height, scope), lock_engine=engine, parsing_backend=backend.name)

        metadata: dict[str, object] = {}
        core_mask = None
        edge_mask = None
        lock_engine_name = 'mask_v1'
        composite_mode = 'feather'

        if scope == 'lower':
            bbox, waist_overlap_px = _expand_bbox_for_lower(settings, bbox, base_img.height)
            core_mask, edge_mask = _build_lower_core_edge_masks(settings, mask)
            lock_engine_name = 'mask_v1_lower_v2'
            composite_mode = 'core+edge'
            metadata.update(
                {
                    'lower_patch_v2': True,
                    'waist_overlap_px': waist_overlap_px,
                    'core_mask_used': core_mask is not None,
                    'composite_mode': 'core+edge',
                }
            )

        if settings.vision_debug_save_masks:
            await _save_debug_artifacts(
                storage,
                job_id,
                base_img,
                parsing_result.class_map,
                mask,
                bbox,
                scope=scope,
                core_mask=core_mask,
                edge_mask=edge_mask,
            )

        return LockEnginePlan(
            crop_rect=bbox,
            lock_engine=lock_engine_name,
            parsing_backend=backend.name,
            mask=mask,
            core_mask=core_mask,
            edge_mask=edge_mask,
            mask_area_ratio=area,
            composite_mode=composite_mode,
            metadata=metadata,
        )
    except Exception:
        logger.exception('Parsing backend failed, fallback to crop_v1', extra={'job_id': job_id, 'scope': scope})
        engine = 'crop_v1_lower_v2_fallback' if scope == 'lower' else 'crop_v1_fallback'
        return LockEnginePlan(crop_rect=_expand_fallback_rect(settings, fallback_rect, base_img.height, scope), lock_engine=engine, parsing_backend=backend.name)


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

    if plan.lock_engine == 'mask_v1_lower_v2' and plan.mask is not None:
        x0, y0, x1, y1 = plan.crop_rect
        if plan.core_mask is not None and plan.edge_mask is not None:
            core_crop = plan.core_mask[y0:y1, x0:x1]
            edge_crop = plan.edge_mask[y0:y1, x0:x1]
            return composite_patch_with_core_edge(base_image_bytes, edited_patch_bytes, plan.crop_rect, core_crop, edge_crop)
        mask_crop = plan.mask[y0:y1, x0:x1]
        alpha = feather_mask(mask_crop, settings.lower_edge_feather_px)
        return composite_patch_with_mask(base_image_bytes, edited_patch_bytes, plan.crop_rect, alpha)

    return composite_crop_back(
        base_image_bytes,
        edited_patch_bytes,
        plan.crop_rect,
        feather_px=settings.vision_mask_feather_px,
    )


def _build_target_mask(settings: Settings, mask_raw: np.ndarray, scope: str) -> np.ndarray:
    if scope == 'lower':
        return dilate_mask_asymmetric(
            mask_raw,
            up_px=settings.lower_mask_dilate_up_px,
            side_px=settings.lower_mask_dilate_side_px,
            down_px=settings.lower_mask_dilate_down_px,
        )
    return dilate_mask(mask_raw, settings.vision_mask_dilate_px)


def _expand_bbox_for_lower(
    settings: Settings,
    bbox: tuple[int, int, int, int],
    image_height: int,
) -> tuple[tuple[int, int, int, int], int]:
    x0, y0, x1, y1 = bbox
    base_h = max(1, y1 - y0)
    ratio_extension = int(round(base_h * float(settings.lower_min_top_extension_ratio)))
    overlap = max(int(settings.lower_waist_overlap_px), ratio_extension)
    y0 = max(0, y0 - overlap)
    return (x0, y0, x1, min(image_height, y1)), overlap


def _expand_fallback_rect(
    settings: Settings,
    rect: tuple[int, int, int, int],
    image_height: int,
    scope: str,
) -> tuple[int, int, int, int]:
    if scope != 'lower':
        return rect
    expanded, _ = _expand_bbox_for_lower(settings, rect, image_height)
    return expanded


def _build_lower_core_edge_masks(settings: Settings, mask: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
    core = erode_mask(mask, settings.lower_core_erode_px)
    if core is None or core.shape != mask.shape:
        return None, None
    edge = np.where(mask > core, 255, 0).astype(np.uint8)
    edge = feather_mask(edge, settings.lower_edge_feather_px)
    return core, edge


async def _save_debug_artifacts(
    storage: StorageBackend,
    job_id: str,
    base_image: Image.Image,
    class_map: np.ndarray,
    mask: np.ndarray,
    bbox: tuple[int, int, int, int],
    *,
    scope: str,
    core_mask: np.ndarray | None,
    edge_mask: np.ndarray | None,
) -> None:
    prefix = f'tryon/jobs/{job_id}/debug'

    class_norm = class_map.astype(np.float32)
    class_norm = (255 * (class_norm - class_norm.min()) / (class_norm.max() - class_norm.min() + 1e-6)).astype(np.uint8)
    class_img = Image.fromarray(class_norm, mode='L')

    x0, y0, x1, y1 = bbox
    crop_img = base_image.crop((x0, y0, x1, y1))

    overlay = base_image.copy()
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 40, 40), width=3)

    artifacts: list[tuple[str, Image.Image]] = [
        ('parsing_class_preview.png', class_img),
        ('raw_mask.png', Image.fromarray(mask, mode='L')),
        ('bbox_crop.png', crop_img),
        ('bbox_overlay.png', overlay),
    ]

    if scope == 'lower':
        artifacts.extend(
            [
                ('lower_mask_raw.png', Image.fromarray(mask, mode='L')),
                ('lower_bbox.png', overlay),
            ]
        )
        if core_mask is not None:
            artifacts.append(('lower_mask_core.png', Image.fromarray(core_mask, mode='L')))
        if edge_mask is not None:
            artifacts.append(('lower_mask_edge.png', Image.fromarray(edge_mask, mode='L')))
            preview = np.maximum(core_mask if core_mask is not None else np.zeros_like(edge_mask), edge_mask).astype(np.uint8)
            artifacts.append(('lower_composite_preview.png', Image.fromarray(preview, mode='L')))

    for name, image in artifacts:
        out = BytesIO()
        image.save(out, format='PNG')
        await storage.put_bytes(f'{prefix}/{name}', out.getvalue(), content_type='image/png')
