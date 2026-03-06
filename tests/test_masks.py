from __future__ import annotations

import pytest

np = pytest.importorskip("numpy", reason="numpy is required for mask engine tests")

from app.services.vision.base import ParsingResult
from app.services.vision.masks import build_scope_mask, dilate_mask, feather_mask, mask_bbox


def _fake_parsing() -> ParsingResult:
    class_map = np.zeros((10, 10), dtype=np.int32)
    class_map[1:4, 2:8] = 5  # upper-clothes
    class_map[4:8, 2:8] = 9  # pants
    class_map[8:10, 3:7] = 18  # shoes
    labels = {'background': 0, 'upper-clothes': 5, 'pants': 9, 'left-shoe': 18, 'person': 1}
    return ParsingResult(class_map=class_map, labels=labels, width=10, height=10, metadata={})


def test_build_scope_mask_supports_upper_lower_feet() -> None:
    parsing = _fake_parsing()
    upper = build_scope_mask(parsing, 'upper')
    lower = build_scope_mask(parsing, 'lower')
    feet = build_scope_mask(parsing, 'feet')

    assert upper[2, 3] == 255
    assert upper[6, 3] == 0
    assert lower[6, 3] == 255
    assert lower[2, 3] == 0
    assert feet[9, 4] == 255


def test_dilate_and_feather_mask_do_not_crash() -> None:
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[8:12, 8:12] = 255

    dilated = dilate_mask(mask, 2)
    feathered = feather_mask(dilated, 2)

    assert dilated.shape == mask.shape
    assert feathered.shape == mask.shape


def test_mask_bbox_is_calculated() -> None:
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:5, 3:6] = 255
    bbox = mask_bbox(mask, margin_px=1)
    assert bbox == (2, 1, 7, 6)


def test_scope_mask_fallback_to_empty_when_no_labels() -> None:
    parsing = ParsingResult(
        class_map=np.zeros((8, 8), dtype=np.int32),
        labels={'background': 0},
        width=8,
        height=8,
        metadata={},
    )
    mask = build_scope_mask(parsing, 'upper')
    assert mask.max() == 0
