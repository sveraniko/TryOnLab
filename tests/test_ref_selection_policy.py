from app.worker.executor import select_reference_inputs


def test_selected_refs_obey_provider_limit() -> None:
    selected = select_reference_inputs(
        clean_key='clean',
        fit_key='fit',
        extra_fit_keys=['x1', 'x2'],
        scope='full',
        reference_strategy='fit_priority',
        provider_image_input_limit=3,
    )
    refs = [x for x in [selected['clean'], selected['fit'], selected['extra']] if x]
    assert len(refs) <= 2


def test_multi_fit_chooses_fit_plus_extra() -> None:
    selected = select_reference_inputs(
        clean_key='clean',
        fit_key='fit',
        extra_fit_keys=['x1'],
        scope='full',
        reference_strategy='multi_fit',
        provider_image_input_limit=3,
    )
    assert selected['fit'] == 'fit'
    assert selected['extra'] == 'x1'


def test_clean_priority_chooses_clean_plus_fit() -> None:
    selected = select_reference_inputs(
        clean_key='clean',
        fit_key='fit',
        extra_fit_keys=['x1'],
        scope='upper',
        reference_strategy='clean_priority',
        provider_image_input_limit=3,
    )
    assert selected['clean'] == 'clean'
    assert selected['fit'] == 'fit'


def test_fit_only_ignores_clean() -> None:
    selected = select_reference_inputs(
        clean_key='clean',
        fit_key='fit',
        extra_fit_keys=['x1'],
        scope='lower',
        reference_strategy='fit_only',
        provider_image_input_limit=3,
    )
    assert selected['fit'] == 'fit'
    assert selected['clean'] is None
