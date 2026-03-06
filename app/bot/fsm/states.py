from aiogram.fsm.state import State, StatesGroup


class WizardStates(StatesGroup):
    await_product_photo = State()
    await_user_photo_upload = State()
    await_measurements_text = State()
    await_look_item_photo = State()
