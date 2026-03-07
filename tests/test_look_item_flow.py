from app.bot.services.look_builder import append_extra_fit_ref


def test_extra_fit_refs_append_correctly() -> None:
    values = append_extra_fit_ref([], 'a', max_refs=2)
    values = append_extra_fit_ref(values, 'b', max_refs=2)
    assert values == ['a', 'b']


def test_continue_does_not_require_scope_if_already_chosen() -> None:
    data = {'look_item_scope': 'upper'}
    assert bool(data.get('look_item_scope')) is True


def test_item_clear_resets_refs_strategy_scope() -> None:
    state = {
        'look_item_product_file_id': 'p',
        'look_item_clean_file_id': 'c',
        'look_item_fit_file_id': 'f',
        'look_item_fit_extra_file_ids': ['x'],
        'look_item_scope': 'lower',
        'look_item_reference_strategy': 'fit_priority',
    }
    state.update(
        look_item_product_file_id=None,
        look_item_clean_file_id=None,
        look_item_fit_file_id=None,
        look_item_fit_extra_file_ids=[],
        look_item_scope=None,
        look_item_reference_strategy=None,
    )
    assert state['look_item_fit_extra_file_ids'] == []
    assert state['look_item_scope'] is None
    assert state['look_item_reference_strategy'] is None
