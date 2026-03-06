from app.services.prompts import VIDEO_PRESETS, build_tryon_prompt, build_video_prompt


def test_build_tryon_prompt_with_measurements_and_fit() -> None:
    prompt = build_tryon_prompt('slim', {'height_cm': 176, 'chest': 98, 'waist': 82})
    assert 'Fit preference: slim; slightly closer fit but realistic.' in prompt
    assert 'Measurements: height_cm=176, chest=98, waist=82.' in prompt
    assert 'keep the person photo unchanged' in prompt


def test_build_tryon_prompt_without_measurements() -> None:
    prompt = build_tryon_prompt('regular', None)
    assert 'Fit preference: regular; natural fit.' in prompt
    assert 'Measurements:' not in prompt


def test_build_video_prompt_for_all_presets() -> None:
    for preset in VIDEO_PRESETS:
        prompt = build_video_prompt(preset)
        assert VIDEO_PRESETS[preset] in prompt
        assert 'Generate a short photorealistic video' in prompt
