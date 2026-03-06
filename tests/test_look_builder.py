import asyncio

from app.bot.services.look_builder import (
    choose_force_lock,
    choose_person_input,
    new_look_step,
    push_look_step,
    reset_look,
    resolve_person_image_bytes,
    undo_look_step,
)


def test_look_stack_push_pop_reset() -> None:
    state = {'look_stack': [], 'look_steps': 0, 'look_base_job_id': None}
    step1 = new_look_step(job_id='job-1', result_image_url='https://cdn/look1.jpg', mode='strict', scope='upper', provider='dummy')
    step2 = new_look_step(job_id='job-2', result_image_url='https://cdn/look2.jpg', mode='creative', scope='lower', provider='dummy')

    pushed = push_look_step(state, step1)
    pushed = push_look_step(pushed, step2)

    assert pushed['look_steps'] == 2
    assert pushed['look_base_job_id'] == 'job-2'

    undone = undo_look_step(pushed)
    assert undone['look_steps'] == 1
    assert undone['look_base_job_id'] == 'job-1'

    reset = reset_look(undone)
    assert reset['look_steps'] == 0
    assert reset['look_stack'] == []
    assert reset['look_base_job_id'] is None
    assert reset['look_item_product_file_id'] is None
    assert reset['look_item_scope'] is None


def test_choose_person_input_prefers_base_job_id() -> None:
    with_base = choose_person_input(look_base_job_id='job-123', active_user_photo_id=12)
    assert with_base == {'base_job_id': 'job-123', 'user_photo_id': None}

    from_user_photo = choose_person_input(look_base_job_id=None, active_user_photo_id=12)
    assert from_user_photo == {'base_job_id': None, 'user_photo_id': 12}


def test_resolve_person_image_bytes_fetches_fresh_url_from_job() -> None:
    class FakeApi:
        async def get_job(self, job_id: str):
            assert job_id == 'job-123'
            return {'result_image_url': 'https://fresh/url.jpg'}

    async def fake_reader(url: str) -> bytes:
        assert url == 'https://fresh/url.jpg'
        return b'fresh-bytes'

    resolved = asyncio.run(resolve_person_image_bytes(api_client=FakeApi(), base_job_id='job-123', read_bytes=fake_reader))
    assert resolved == b'fresh-bytes'


def test_resolve_person_image_bytes_without_base_job() -> None:
    async def fake_reader(url: str) -> bytes:
        _ = url
        return b'unused'

    assert asyncio.run(resolve_person_image_bytes(api_client=object(), base_job_id=None, read_bytes=fake_reader)) is None


def test_choose_force_lock_defaults_to_enabled() -> None:
    assert choose_force_lock(None) is True
    assert choose_force_lock(True) is True
    assert choose_force_lock(False) is False
