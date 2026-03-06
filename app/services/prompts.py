from __future__ import annotations

from typing import Any

SYSTEM_RULES = (
    'You are an image editing assistant. '\
    'Goal: keep the person photo unchanged (identity, face, hair, body shape, pose, background). '\
    'Replace only the clothing with the garment from the product photo. '\
    'Photorealistic. No text, no logos, no watermark. No extra accessories. '\
    'Do not change skin tone or facial features. Preserve original lighting direction.'
)

FIT_DIRECTIVES: dict[str, str] = {
    'slim': 'Fit preference: slim; slightly closer fit but realistic.',
    'regular': 'Fit preference: regular; natural fit.',
    'oversize': 'Fit preference: oversize; slightly looser fit but realistic.',
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

PROMPT_VERSION = 'pr06.v1'


def build_tryon_prompt(fit_pref: str | None, measurements: dict[str, Any] | None) -> str:
    fit_value = (fit_pref or 'regular').strip().lower()
    fit_line = FIT_DIRECTIVES.get(fit_value, FIT_DIRECTIVES['regular'])

    lines = [
        SYSTEM_RULES,
        'Use PERSON_IMAGE as the base image.',
        'Put the clothing from GARMENT_IMAGE onto the person.',
        "Match the garment's exact color, pattern, texture, and silhouette.",
        fit_line,
        'Keep: face, hair, body proportions, pose, hands, background.',
        'Change only: the clothing area needed to wear the garment.',
        'Add realistic fabric folds and seams. Keep the photo natural.',
    ]

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
