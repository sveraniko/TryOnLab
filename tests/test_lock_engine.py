from __future__ import annotations

from io import BytesIO

import pytest

Image = pytest.importorskip("PIL.Image", reason="Pillow is required for lock engine tests")

from app.services.vision.lock_engine import composite_crop_back, compute_scope_crop_rect


def _img_bytes(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    image = Image.new('RGB', size, color)
    out = BytesIO()
    image.save(out, format='JPEG')
    return out.getvalue()


def test_compute_scope_crop_rect_bounds() -> None:
    width, height = 200, 300
    for scope in ('upper', 'lower', 'feet', 'full', 'unknown'):
        x0, y0, x1, y1 = compute_scope_crop_rect(width, height, scope)
        assert 0 <= x0 < x1 <= width
        assert 0 <= y0 < y1 <= height


def test_composite_crop_back_changes_only_crop_area() -> None:
    base_bytes = _img_bytes((10, 10, 10), (80, 80))
    crop_rect = (20, 20, 60, 60)
    edited_crop = _img_bytes((240, 0, 0), (40, 40))

    result_bytes = composite_crop_back(base_bytes, edited_crop, crop_rect, feather_px=0)
    img = Image.open(BytesIO(result_bytes)).convert('RGB')

    outside_pixel = img.getpixel((10, 10))
    inside_pixel = img.getpixel((40, 40))

    assert outside_pixel[0] < 30 and outside_pixel[1] < 30 and outside_pixel[2] < 30
    assert inside_pixel[0] > 200 and inside_pixel[1] < 40 and inside_pixel[2] < 40
