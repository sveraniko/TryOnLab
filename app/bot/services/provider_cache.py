from __future__ import annotations

import time


def is_provider_cache_fresh(cached_at: float | None, ttl_seconds: int, now: float | None = None) -> bool:
    if not cached_at:
        return False
    current = now if now is not None else time.time()
    return (current - cached_at) < ttl_seconds
