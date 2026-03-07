from __future__ import annotations

from typing import Any

PROMPT_VERSION = 'pr09.v1'

BASE_IDENTITY_RULES = (
    'Keep identity and scene fixed: preserve face, hair, body shape, pose, hands, and background. '
    'No text, logos, or watermarks. Photorealistic output only.'
)

FIT_DIRECTIVES: dict[str, str] = {
    'slim': 'Fit preference: slim; slightly closer fit but realistic.',
    'regular': 'Fit preference: regular; natural fit.',
    'oversize': 'Fit preference: oversize; slightly looser fit but realistic.',
}

STRICT_SCOPE_RULES: dict[str, list[str]] = {
    'upper': [
        'Edit scope: upper body only (tops, jackets, coats).',
        'Keep the original outfit unchanged outside the edited region.',
        'Do NOT change shorts, pants, skirt, legs, or shoes.',
        'Do NOT add a skirt.',
    ],
    'lower': [
        'Edit scope: lower body only (pants, skirts, shorts).',
        'Replace the existing lower-body garment completely with these pants.',
        'Do not keep the original shorts visible.',
        'Keep upper body clothing unchanged.',
        'Preserve the waistband shape of the new garment clearly.',
        'Do not alter shoes unless they are naturally occluded by the pants.',
        'Keep the original outfit unchanged outside the edited region.',
        'Do NOT change top, jacket, arms, or upper-body clothing.',
        'Do NOT change shoes unless scope is feet.',
    ],
    'feet': [
        'Edit scope: feet only (shoes and socks area).',
        'Keep the original outfit unchanged outside the edited region.',
        'Do NOT change clothing outside shoes/socks area.',
        'Only change shoes/socks area.',
    ],
    'full': [
        'Edit scope: full body clothing edit.',
        'Preserve identity and background; do not alter anatomy unrealistically.',
    ],
}

CREATIVE_SCOPE_RULES: dict[str, list[str]] = {
    'upper': [
        'Creative mode: build a harmonious outfit around the product.',
        'You may adapt lower garments and shoes to match the style.',
    ],
    'lower': [
        'Creative mode: build a harmonious outfit around the product.',
        'You may adapt top layers and shoes to match the style.',
    ],
    'feet': [
        'Creative mode: build a harmonious outfit around the footwear.',
        'Minor outfit coordination is allowed while preserving identity and scene.',
    ],
    'full': [
        'Creative mode: style a coherent full look around the product.',
    ],
}

VIDEO_SYSTEM_RULES = (
    'Generate a short photorealistic video from the provided TRYON_IMAGE. '
    "Keep the person's identity, face, and body intact. "
    'No text, no logos, no watermark. '
    'Natural motion, stable anatomy. No distortion.'
)

VIDEO_PRESETS: dict[int, str] = {
    1: 'The person takes two small natural steps toward the camera, then turns 45 degrees to show the side fit, pauses, and returns to facing the camera. Slow, smooth motion. Keep background and lighting consistent.',
    2: 'Slow 180-degree turn in place to show front and side, then stop facing the camera. Minimal movement, stable anatomy. Keep the face consistent.',
    3: 'One to two confident catwalk steps forward, then a simple pose: slight hip shift and head turn. Smooth motion. Keep clothing details sharp and realistic.',
    4: 'Subtle arm movement: the person slightly raises and opens arms to show shoulder and chest fit, then relaxes. Keep hands natural and correct.',
    5: 'Very subtle body sway and weight shift to show how the fabric drapes. No big gestures. Keep the garment texture and seams crisp, no distortions.',
}


def build_tryon_prompt(
    mode: str | None,
    scope: str | None,
    fit_pref: str | None,
    measurements: dict[str, Any] | None,
    *,
    force_lock: bool = False,
    has_clean_ref: bool = True,
    has_fit_ref: bool = False,
    reference_strategy: str | None = None,
) -> str:
    normalized_mode = (mode or 'strict').strip().lower()
    if normalized_mode not in {'strict', 'creative'}:
        normalized_mode = 'strict'

    normalized_scope = (scope or 'full').strip().lower()
    if normalized_scope not in {'upper', 'lower', 'feet', 'full'}:
        normalized_scope = 'full'

    fit_value = (fit_pref or 'regular').strip().lower()
    fit_line = FIT_DIRECTIVES.get(fit_value, FIT_DIRECTIVES['regular'])
    strategy = (reference_strategy or 'auto').strip().lower()

    lines = [
        BASE_IDENTITY_RULES,
        'Use PERSON_IMAGE as base.',
        fit_line,
        f'Mode: {normalized_mode}.',
        f'Scope: {normalized_scope}.',
    ]

    if has_clean_ref and has_fit_ref:
        lines.extend(
            [
                'Use GARMENT_CLEAN_IMAGE as the primary source of garment details, material, closures, and exact design.',
                'Use GARMENT_FIT_REFERENCE_IMAGE as the primary source of silhouette, fit, rise, drape, and length.',
                'Do not mix roles: clean reference controls details, fit reference controls silhouette/fit.',
            ]
        )
    elif has_clean_ref:
        lines.append('Use GARMENT_CLEAN_IMAGE as the primary source of garment details and exact design.')
    elif has_fit_ref:
        lines.append('Use GARMENT_FIT_REFERENCE_IMAGE as the primary source of silhouette, fit, rise, drape, and length.')
    else:
        lines.append('Use GARMENT_IMAGE as product reference.')

    if strategy == 'clean_priority':
        lines.append('Use GARMENT_CLEAN_IMAGE as the primary source of garment details and exact design.')
        lines.append('Use fit reference only as a secondary guide for silhouette.')
    elif strategy == 'fit_priority':
        lines.append('Use GARMENT_FIT_REFERENCE_IMAGE as the primary source of silhouette, fit, rise, drape, and length.')
        lines.append('Use clean reference only as a secondary source for details.')
    elif strategy == 'fit_only':
        lines.append('Rely entirely on fit reference for silhouette and garment appearance.')
    elif strategy == 'clean_only':
        lines.append('Rely entirely on clean reference for garment appearance.')
    elif strategy == 'multi_fit':
        lines.append('Use both fit references to infer consistent silhouette and how the garment sits on the body.')
    if has_fit_ref and normalized_scope == 'lower':
        lines.extend(
            [
                'Follow the lower-body silhouette from GARMENT_FIT_REFERENCE_IMAGE closely.',
                'Preserve the waistband rise, volume at hips, taper, and length.',
            ]
        )
    if has_fit_ref and normalized_scope == 'upper':
        lines.append('Follow sleeve shape, shoulder volume, jacket length, and closure placement from fit reference.')


    if has_fit_ref and normalized_scope in {'lower', 'full'} and strategy in {'fit_priority', 'multi_fit'}:
        lines.append('Preserve waistband rise, pleat structure, hip volume, taper, and length according to fit reference.')
    if force_lock and normalized_scope != 'full':
        lines.extend([
            'Do not change anything outside the edited region.',
            'Do not add skirt/pants/shoes unless scope demands.',
        ])

    if normalized_mode == 'strict':
        lines.extend(STRICT_SCOPE_RULES[normalized_scope])
    else:
        lines.extend(
            [
                'Allow tasteful styling for a harmonious outfit while preserving identity and scene.',
                'Face, hair, pose, and background must remain unchanged.',
            ]
        )
        lines.extend(CREATIVE_SCOPE_RULES[normalized_scope])

    compact = _compact_measurements(measurements)
    if compact:
        lines.extend(
            [
                'Body proportions reference (do not redesign the body):',
                f'Measurements: {compact}.',
                'Use this only to keep garment proportions realistic, not to change identity.',
            ]
        )

    return '\n'.join(lines)


def build_video_prompt(preset: int) -> str:
    if preset not in VIDEO_PRESETS:
        raise ValueError('Video preset must be in range 1..5')

    return f'{VIDEO_SYSTEM_RULES}\n{VIDEO_PRESETS[preset]}'


def _compact_measurements(measurements: dict[str, Any] | None) -> str:
    if not measurements:
        return ''

    chunks: list[str] = []
    for key, value in measurements.items():
        if value is None:
            continue
        chunks.append(f'{key}={value}')

    return ', '.join(chunks)
