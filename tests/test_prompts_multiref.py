from app.services.prompts import build_tryon_prompt


def test_prompt_clean_only_has_clean_role() -> None:
    prompt = build_tryon_prompt('strict', 'full', 'regular', None, has_clean_ref=True, has_fit_ref=False)
    assert 'GARMENT_CLEAN_IMAGE' in prompt
    assert 'GARMENT_FIT_REFERENCE_IMAGE' not in prompt


def test_prompt_fit_only_has_fit_role() -> None:
    prompt = build_tryon_prompt('strict', 'lower', 'regular', None, has_clean_ref=False, has_fit_ref=True)
    assert 'GARMENT_CLEAN_IMAGE' not in prompt
    assert 'GARMENT_FIT_REFERENCE_IMAGE' in prompt
    assert 'Follow the lower-body silhouette from GARMENT_FIT_REFERENCE_IMAGE closely.' in prompt


def test_prompt_with_both_refs_splits_roles() -> None:
    prompt = build_tryon_prompt('strict', 'upper', 'regular', None, has_clean_ref=True, has_fit_ref=True)
    assert 'GARMENT_CLEAN_IMAGE as the primary source of garment details' in prompt
    assert 'GARMENT_FIT_REFERENCE_IMAGE as the primary source of silhouette' in prompt
    assert 'Do not mix roles: clean reference controls details, fit reference controls silhouette/fit.' in prompt
