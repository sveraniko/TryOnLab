from app.bot.services.look_builder import choose_force_lock, default_patch_mode_for_item


def test_lower_item_starts_with_patch_off() -> None:
    assert default_patch_mode_for_item('lower', True) is False
    assert choose_force_lock(default_patch_mode_for_item('lower', True), scope='lower') is False


def test_upper_item_keeps_global_patch_mode() -> None:
    assert default_patch_mode_for_item('upper', True) is True
    assert default_patch_mode_for_item('upper', False) is False
