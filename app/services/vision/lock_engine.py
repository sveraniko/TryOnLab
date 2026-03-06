from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

ScopeRect = tuple[int, int, int, int]

_SCOPE_RATIOS: dict[str, tuple[float, float, float, float]] = {
    'upper': (0.12, 0.08, 0.88, 0.62),
    'lower': (0.12, 0.40, 0.88, 0.98),
    'feet': (0.10, 0.72, 0.90, 0.98),
    'full': (0.0, 0.0, 1.0, 1.0),
}


def compute_scope_crop_rect(width: int, height: int, scope: str) -> ScopeRect:
    normalized_scope = scope if scope in _SCOPE_RATIOS else 'full'
    x0r, y0r, x1r, y1r = _SCOPE_RATIOS[normalized_scope]
    x0 = int(round(width * x0r))
    y0 = int(round(height * y0r))
    x1 = int(round(width * x1r))
    y1 = int(round(height * y1r))
    x0 = max(0, min(width - 1, x0))
    y0 = max(0, min(height - 1, y0))
    x1 = max(x0 + 1, min(width, x1))
    y1 = max(y0 + 1, min(height, y1))
    return x0, y0, x1, y1


def build_feather_mask(size: tuple[int, int], feather_px: int = 12) -> Image.Image:
    w, h = size
    mask = Image.new('L', size, 255)
    if feather_px <= 0:
        return mask

    draw = ImageDraw.Draw(mask)
    for i in range(feather_px):
        alpha = int(255 * (i + 1) / feather_px)
        draw.rectangle((i, i, w - 1 - i, h - 1 - i), outline=alpha)
    return mask


def composite_crop_back(
    base_image_bytes: bytes,
    edited_crop_bytes: bytes,
    crop_rect: ScopeRect,
    feather_px: int = 12,
    output_format: str = 'JPEG',
) -> bytes:
    base = Image.open(BytesIO(base_image_bytes)).convert('RGB')
    crop = Image.open(BytesIO(edited_crop_bytes)).convert('RGB')

    x0, y0, x1, y1 = crop_rect
    target_size = (x1 - x0, y1 - y0)
    crop = crop.resize(target_size)
    mask = build_feather_mask(target_size, feather_px=feather_px)

    canvas = base.copy()
    canvas.paste(crop, (x0, y0), mask)

    out = BytesIO()
    canvas.save(out, format=output_format)
    return out.getvalue()
