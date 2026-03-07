from app.bot.services.look_builder import resolve_reference_strategy
from app.worker.executor import resolve_effective_strategy


def test_auto_chooses_expected_strategy_by_scope_and_refs() -> None:
    assert resolve_effective_strategy('auto', scope='lower', clean_exists=True, fit_exists=True) == 'fit_priority'
    assert resolve_effective_strategy('auto', scope='full', clean_exists=False, fit_exists=True) == 'fit_priority'
    assert resolve_effective_strategy('auto', scope='upper', clean_exists=True, fit_exists=False) == 'clean_priority'


def test_strategy_modes_validate() -> None:
    for strategy in ['fit_priority', 'clean_priority', 'fit_only', 'clean_only', 'multi_fit']:
        assert resolve_reference_strategy(strategy, scope='full', clean_exists=True, fit_exists=True, extra_fit_count=1) == strategy
