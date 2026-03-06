from app.bot.services.provider_cache import is_provider_cache_fresh


def test_is_provider_cache_fresh() -> None:
    assert is_provider_cache_fresh(cached_at=100.0, ttl_seconds=60, now=120.0) is True
    assert is_provider_cache_fresh(cached_at=100.0, ttl_seconds=60, now=161.0) is False
    assert is_provider_cache_fresh(cached_at=None, ttl_seconds=60, now=120.0) is False
