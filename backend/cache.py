"""Redis caching utility for Lightline VPN Panel."""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get('REDIS_URL', '')

_redis = None


async def get_redis():
    """Get or create the Redis connection."""
    global _redis
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        return None
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected")
        return _redis
    except Exception as e:
        logger.warning(f"Redis unavailable, caching disabled: {e}")
        _redis = None
        return None


async def cache_get(key: str) -> Optional[str]:
    """Get a value from cache. Returns None if Redis unavailable or key missing."""
    r = await get_redis()
    if not r:
        return None
    try:
        return await r.get(key)
    except Exception:
        return None


async def cache_set(key: str, value: str, ttl: int = 300):
    """Set a value in cache with TTL (default 5 min)."""
    r = await get_redis()
    if not r:
        return
    try:
        await r.set(key, value, ex=ttl)
    except Exception:
        pass


async def cache_delete(key: str):
    """Delete a key from cache."""
    r = await get_redis()
    if not r:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


async def cache_get_json(key: str):
    """Get and parse JSON from cache."""
    val = await cache_get(key)
    if val:
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


async def cache_set_json(key: str, data, ttl: int = 300):
    """Serialize to JSON and store in cache."""
    try:
        await cache_set(key, json.dumps(data), ttl)
    except (TypeError, ValueError):
        pass


async def close_redis():
    """Close the Redis connection."""
    global _redis
    if _redis:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None
