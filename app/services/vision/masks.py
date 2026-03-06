from __future__ import annotations

import numpy as np

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency in tests
    cv2 = None

from app.services.vision.base import ParsingResult

Scope = str

_SCOPE_LABEL_GROUPS: dict[str, tuple[str, ...]] = {
    'upper': ('upper-clothes', 'coat', 'jacket', 'dress-upper', 'dress', 'torso-skin'),
    'lower': ('pants', 'skirt', 'dress-lower', 'shorts', 'legs'),
    'feet': ('shoes', 'left-shoe', 'right-shoe', 'socks', 'feet-lower'),
    'full': ('person',),
}

_SILHOUETTE_LABELS = ('person', 'foreground', 'human', 'body')


def _empty_mask(height: int, width: int) -> np.ndarray:
    return np.zeros((height, width), dtype=np.uint8)


def build_scope_mask(parsing_result: ParsingResult, scope: Scope) -> np.ndarray:
    normalized_scope = scope if scope in {'upper', 'lower', 'feet', 'full'} else 'full'
    class_map = parsing_result.class_map
    labels = parsing_result.labels

    mask = _empty_mask(parsing_result.height, parsing_result.width)
    label_ids = [labels[name] for name in _SCOPE_LABEL_GROUPS.get(normalized_scope, ()) if name in labels]
    for label_id in label_ids:
        mask[class_map == label_id] = 255

    if mask.max() == 0:
        silhouette = _build_silhouette_mask(class_map, labels)
        if silhouette.max() > 0:
            mask = _split_silhouette_by_scope(silhouette, normalized_scope)

    return mask


def _build_silhouette_mask(class_map: np.ndarray, labels: dict[str, int]) -> np.ndarray:
    mask = np.zeros_like(class_map, dtype=np.uint8)
    ids = [labels[name] for name in _SILHOUETTE_LABELS if name in labels]
    for label_id in ids:
        mask[class_map == label_id] = 255
    return mask


def _split_silhouette_by_scope(silhouette: np.ndarray, scope: Scope) -> np.ndarray:
    if scope == 'full':
        return silhouette

    ys, _ = np.where(silhouette > 0)
    if ys.size == 0:
        return silhouette

    top = int(ys.min())
    bottom = int(ys.max())
    body_h = max(1, bottom - top + 1)

    upper_end = top + int(body_h * 0.58)
    lower_start = top + int(body_h * 0.48)
    feet_start = top + int(body_h * 0.80)

    mask = np.zeros_like(silhouette, dtype=np.uint8)
    if scope == 'upper':
        mask[top:upper_end + 1, :] = silhouette[top:upper_end + 1, :]
    elif scope == 'lower':
        mask[lower_start:bottom + 1, :] = silhouette[lower_start:bottom + 1, :]
    elif scope == 'feet':
        mask[feet_start:bottom + 1, :] = silhouette[feet_start:bottom + 1, :]
    else:
        mask = silhouette
    return mask


def dilate_mask(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    if cv2 is None:
        return mask
    kernel = np.ones((px * 2 + 1, px * 2 + 1), dtype=np.uint8)
    return cv2.dilate(mask, kernel, iterations=1)


def feather_mask(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    if cv2 is None:
        return mask
    kernel_size = px * 2 + 1
    blurred = cv2.GaussianBlur(mask, (kernel_size, kernel_size), sigmaX=0)
    return np.clip(blurred, 0, 255).astype(np.uint8)


def mask_bbox(mask: np.ndarray, margin_px: int) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask > 0)
    if ys.size == 0 or xs.size == 0:
        return None

    h, w = mask.shape
    x0 = max(0, int(xs.min()) - margin_px)
    y0 = max(0, int(ys.min()) - margin_px)
    x1 = min(w, int(xs.max()) + 1 + margin_px)
    y1 = min(h, int(ys.max()) + 1 + margin_px)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1
