from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image


def composite_patch_with_mask(
    base_image_bytes: bytes,
    edited_patch_bytes: bytes,
    bbox: tuple[int, int, int, int],
    alpha_mask: np.ndarray,
    output_format: str = 'JPEG',
) -> bytes:
    base = Image.open(BytesIO(base_image_bytes)).convert('RGB')
    patch = Image.open(BytesIO(edited_patch_bytes)).convert('RGB')

    x0, y0, x1, y1 = bbox
    target_size = (x1 - x0, y1 - y0)
    resized_patch = patch.resize(target_size)

    if alpha_mask.shape != (target_size[1], target_size[0]):
        alpha_img = Image.fromarray(alpha_mask, mode='L').resize(target_size)
    else:
        alpha_img = Image.fromarray(alpha_mask, mode='L')

    canvas = base.copy()
    canvas.paste(resized_patch, (x0, y0), alpha_img)

    out = BytesIO()
    canvas.save(out, format=output_format)
    return out.getvalue()


def composite_patch_with_core_edge(
    base_image_bytes: bytes,
    edited_patch_bytes: bytes,
    bbox: tuple[int, int, int, int],
    core_mask: np.ndarray,
    edge_mask: np.ndarray,
    output_format: str = 'JPEG',
) -> bytes:
    base = Image.open(BytesIO(base_image_bytes)).convert('RGB')
    patch = Image.open(BytesIO(edited_patch_bytes)).convert('RGB')

    x0, y0, x1, y1 = bbox
    target_size = (x1 - x0, y1 - y0)
    patch = patch.resize(target_size)

    base_arr = np.asarray(base, dtype=np.float32)
    patch_arr = np.asarray(patch, dtype=np.float32)

    if core_mask.shape != (target_size[1], target_size[0]):
        core_mask = np.asarray(Image.fromarray(core_mask, mode='L').resize(target_size), dtype=np.uint8)
    if edge_mask.shape != (target_size[1], target_size[0]):
        edge_mask = np.asarray(Image.fromarray(edge_mask, mode='L').resize(target_size), dtype=np.uint8)

    alpha_core = (core_mask > 0).astype(np.float32)
    alpha_edge = edge_mask.astype(np.float32) / 255.0
    alpha = np.maximum(alpha_core, alpha_edge)

    roi = base_arr[y0:y1, x0:x1, :]
    alpha_3 = alpha[..., None]
    blended = (patch_arr * alpha_3) + (roi * (1.0 - alpha_3))
    base_arr[y0:y1, x0:x1, :] = blended

    out = BytesIO()
    Image.fromarray(np.clip(base_arr, 0, 255).astype(np.uint8), mode='RGB').save(out, format=output_format)
    return out.getvalue()


def mask_area_ratio(mask: np.ndarray) -> float:
    total = mask.size
    if total <= 0:
        return 0.0
    return float((mask > 0).sum()) / float(total)
