"""Async cache manager."""

from app.cache.redis_cache import RedisCache
from app.cache.memory_cache import MemoryCache
from app.utils.config_loader import CONFIG
from typing import Union


async def get_cache() -> Union[RedisCache, MemoryCache]:
    """
    Get async cache instance, preferring Redis if available, falling back to MemoryCache.
    
    Returns:
        RedisCache if Redis is available, otherwise MemoryCache
    """
    try:
        redis_config = CONFIG.get("redis", {})
        
        r = RedisCache(
            host=redis_config.get("host", "localhost"),
            port=redis_config.get("port", 6379),
            max_connections=redis_config.get("max_connections", 50),
            socket_connect_timeout=redis_config.get("socket_connect_timeout", 5),
            socket_timeout=redis_config.get("socket_timeout", 5),
            retry_on_timeout=redis_config.get("retry_on_timeout", True),
            health_check_interval=redis_config.get("health_check_interval", 30)
        )
        
        if await r.ping():
            return r
        else:
            await r.close()
            return MemoryCache()
    except (ConnectionError, Exception) as e:
        print(f"Redis unavailable, falling back to MemoryCache: {str(e)}")
        return MemoryCache()
