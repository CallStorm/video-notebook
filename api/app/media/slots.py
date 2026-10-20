"""Redis concurrency slots for media.pipeline tasks."""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_KEY = "vnb:media:pipeline:slots"


def _client():
    import redis

    from app.core.config import get_settings

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def try_acquire(video_id: int, *, max_concurrent: int, lease_seconds: int) -> bool:
    """Claim a slot for video_id. True if acquired (or already held by same id)."""
    if max_concurrent < 1:
        max_concurrent = 1
    token = f"v{video_id}"
    now = time.time()
    expire_before = now
    lease_until = now + max(60, int(lease_seconds))
    try:
        r = _client()
        # Drop expired leases, then add if under cap (or refresh own token).
        pipe = r.pipeline()
        pipe.zremrangebyscore(_KEY, "-inf", expire_before)
        pipe.zscore(_KEY, token)
        pipe.zcard(_KEY)
        _dropped, own, card = pipe.execute()
        if own is not None:
            r.zadd(_KEY, {token: lease_until})
            return True
        if int(card or 0) >= max_concurrent:
            return False
        # Race-safe-ish: zadd then re-check cardinality
        r.zadd(_KEY, {token: lease_until})
        card2 = r.zcard(_KEY)
        if int(card2 or 0) > max_concurrent and r.zscore(_KEY, token) is not None:
            # Over capacity: only keep if we were already counting ourselves uniquely
            # Drop ourselves if over
            members = r.zrange(_KEY, 0, -1)
            if token in members and len(members) > max_concurrent:
                # Prefer keeping older members; drop self if we're the newest overflow
                r.zrem(_KEY, token)
                return False
        return True
    except Exception:
        logger.exception("media slot acquire failed video_id=%s", video_id)
        # Fail open so a Redis blip does not freeze all fetches
        return True


def release(video_id: int) -> None:
    token = f"v{video_id}"
    try:
        _client().zrem(_KEY, token)
    except Exception:
        logger.exception("media slot release failed video_id=%s", video_id)


def refresh(video_id: int, *, lease_seconds: int) -> None:
    token = f"v{video_id}"
    try:
        _client().zadd(_KEY, {token: time.time() + max(60, int(lease_seconds))})
    except Exception:
        logger.exception("media slot refresh failed video_id=%s", video_id)
