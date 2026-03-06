from app.services.prompts import VIDEO_PRESETS, build_tryon_prompt, build_video_prompt


def test_build_tryon_prompt_strict_upper_with_measurements_and_fit() -> None:
    prompt = build_tryon_prompt('strict', 'upper', 'slim', {'height_cm': 176, 'chest': 98, 'waist': 82})
    assert 'Mode: strict.' in prompt
    assert 'Scope: upper.' in prompt
    assert 'Do NOT change shorts, pants, skirt, legs, or shoes.' in prompt
    assert 'Fit preference: slim; slightly closer fit but realistic.' in prompt
    assert 'Measurements: height_cm=176, chest=98, waist=82.' in prompt


def test_build_tryon_prompt_creative_lower_without_measurements() -> None:
    prompt = build_tryon_prompt('creative', 'lower', 'regular', None)
    assert 'Mode: creative.' in prompt
    assert 'Scope: lower.' in prompt
    assert 'build a harmonious outfit around the product' in prompt
    assert 'Measurements:' not in prompt


def test_build_video_prompt_for_all_presets() -> None:
    for preset in VIDEO_PRESETS:
        prompt = build_video_prompt(preset)
        assert VIDEO_PRESETS[preset] in prompt
        assert 'Generate a short photorealistic video' in prompt


def test_build_tryon_prompt_force_lock_adds_hard_constraints() -> None:
    prompt = build_tryon_prompt('creative', 'upper', 'regular', None, force_lock=True)
    assert 'Do not change anything outside the edited region.' in prompt
    assert 'Do not add skirt/pants/shoes unless scope demands.' in prompt
