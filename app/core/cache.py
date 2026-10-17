import redis
from app.core.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

CACHE_TTL = 3600  # 1 hour


def cache_get(key: str) -> str | None:
    return redis_client.get(key)


def cache_set(key: str, value: str, ttl: int = CACHE_TTL):
    redis_client.setex(key, ttl, value)


def cache_delete(key: str):
    redis_client.delete(key)