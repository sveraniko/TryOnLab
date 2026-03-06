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


def mask_area_ratio(mask: np.ndarray) -> float:
    total = mask.size
    if total <= 0:
        return 0.0
    return float((mask > 0).sum()) / float(total)
