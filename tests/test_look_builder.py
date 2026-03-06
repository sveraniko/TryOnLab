from app.bot.services.look_builder import (
    choose_person_input,
    new_look_step,
    push_look_step,
    reset_look,
    undo_look_step,
)


def test_look_stack_push_pop_reset() -> None:
    state = {'look_stack': [], 'look_steps': 0, 'look_base_job_id': None, 'look_base_image_url': None}
    step1 = new_look_step(job_id='job-1', result_image_url='https://cdn/look1.jpg', mode='strict', scope='upper', provider='dummy')
    step2 = new_look_step(job_id='job-2', result_image_url='https://cdn/look2.jpg', mode='creative', scope='lower', provider='dummy')

    pushed = push_look_step(state, step1)
    pushed = push_look_step(pushed, step2)

    assert pushed['look_steps'] == 2
    assert pushed['look_base_job_id'] == 'job-2'
    assert pushed['look_base_image_url'] == 'https://cdn/look2.jpg'

    undone = undo_look_step(pushed)
    assert undone['look_steps'] == 1
    assert undone['look_base_job_id'] == 'job-1'
    assert undone['look_base_image_url'] == 'https://cdn/look1.jpg'

    reset = reset_look(undone)
    assert reset['look_steps'] == 0
    assert reset['look_stack'] == []
    assert reset['look_base_job_id'] is None
    assert reset['look_base_image_url'] is None
    assert reset['look_item_product_file_id'] is None
    assert reset['look_item_scope'] is None


def test_choose_person_input_prefers_base_url() -> None:
    with_base = choose_person_input(look_base_image_url='https://cdn/base.jpg', active_user_photo_id=12)
    assert with_base == {'person_image_url': 'https://cdn/base.jpg', 'user_photo_id': None}

    from_user_photo = choose_person_input(look_base_image_url=None, active_user_photo_id=12)
    assert from_user_photo == {'person_image_url': None, 'user_photo_id': 12}
