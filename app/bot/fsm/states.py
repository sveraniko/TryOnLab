from aiogram.fsm.state import State, StatesGroup


class WizardStates(StatesGroup):
    await_product_photo = State()
    await_product_clean_photo = State()
    await_product_fit_photo = State()
    await_user_photo_upload = State()
    await_measurements_text = State()
    await_look_item_photo = State()
    await_look_item_clean_photo = State()
    await_look_item_fit_photo = State()
