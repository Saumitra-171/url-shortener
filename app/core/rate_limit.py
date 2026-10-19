import logging
import math
import time
import uuid

import redis
from fastapi import Depends, HTTPException, Request

from app.core.cache import redis_client
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)


def _now() -> float:
    return time.time()  # a function so tests can control the clock


def hit(key: str, limit: int, window: int) -> tuple[bool, int]:
    """Record one request. Returns (allowed, retry_after_seconds)."""
    now = _now()
    redis_key = f"rl:{key}"
    # Sorted-set members must be unique, or two requests in the same instant collapse into one.
    member = f"{now}:{uuid.uuid4().hex[:8]}"
    try:
        # transaction=True wraps the commands in MULTI/EXEC so concurrent requests can't
        # interleave. One network round trip for all five commands.
        pipe = redis_client.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, 0, now - window)   # drop entries older than the window
        pipe.zadd(redis_key, {member: now})                 # record this request
        pipe.zcard(redis_key)                               # how many are in the window now?
        pipe.zrange(redis_key, 0, 0, withscores=True)       # the oldest one, for Retry-After
        pipe.expire(redis_key, window)                      # idle keys clean themselves up
        _, _, count, oldest, _ = pipe.execute()
    except redis.RedisError:
        # Fail open: an outage in the limiter must not take the whole API down.
        logger.warning("Rate limiter unavailable, allowing request (key=%s)", key)
        return True, 0

    if count <= limit:
        return True, 0

    try:
        # Rejected requests don't count, otherwise a client that keeps hammering stays blocked.
        redis_client.zrem(redis_key, member)
    except redis.RedisError:
        pass
    retry_after = max(1, math.ceil(oldest[0][1] + window - now))
    return False, retry_after


def _enforce(key: str, limit: int, window: int) -> None:
    allowed, retry_after = hit(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


def limit_by_ip(name: str, limit: int, window: int):
    """For anonymous endpoints (register, login)."""
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        _enforce(f"{name}:ip:{ip}", limit, window)
    return dependency


def limit_by_user(name: str, limit: int, window: int):
    """For logged-in endpoints. Depends on get_current_user, so anonymous calls get 401 first."""
    def dependency(current_user: User = Depends(get_current_user)) -> None:
        _enforce(f"{name}:user:{current_user.id}", limit, window)
    return dependency