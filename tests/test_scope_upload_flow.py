import asyncio
from types import SimpleNamespace

from app.bot.router import on_product_clean_photo, on_product_fit_photo
from app.bot.ui.screens import Screen


class DummyState:
    def __init__(self):
        self.data = {}

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


class DummyBot:
    async def get_file(self, _):
        return None


def _message(file_id: str = 'f1'):
    return SimpleNamespace(
        photo=[SimpleNamespace(file_id=file_id)],
        chat=SimpleNamespace(id=1),
        message_id=9,
    )


def test_upload_clean_does_not_redirect_to_product_scope(monkeypatch) -> None:
    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr('app.bot.router.try_delete', noop)
    monkeypatch.setattr('app.bot.router._client', noop)
    monkeypatch.setattr('app.bot.router._render_current', noop)

    state = DummyState()
    asyncio.run(on_product_clean_photo(_message('clean1'), state, DummyBot(), settings=None))
    assert state.data['screen'] == Screen.PRODUCT.value


def test_upload_fit_does_not_redirect_to_product_scope(monkeypatch) -> None:
    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr('app.bot.router.try_delete', noop)
    monkeypatch.setattr('app.bot.router._client', noop)
    monkeypatch.setattr('app.bot.router._render_current', noop)

    state = DummyState()
    asyncio.run(on_product_fit_photo(_message('fit1'), state, DummyBot(), settings=None))
    assert state.data['screen'] == Screen.PRODUCT.value
