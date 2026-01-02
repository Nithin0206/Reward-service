#!/usr/bin/env python3
"""Script to clear all data from Redis cache."""

import asyncio
import aioredis
from app.utils.config_loader import CONFIG


async def clear_redis():
    """Clear all keys from Redis."""
    redis_config = CONFIG.get("redis", {})
    host = redis_config.get("host", "localhost")
    port = redis_config.get("port", 6379)
    
    connection_url = f"redis://{host}:{port}"
    
    try:
        print(f"Connecting to Redis at {host}:{port}...")
        redis = await aioredis.from_url(
            connection_url,
            decode_responses=True
        )
        
        # Test connection
        await redis.ping()
        print("✓ Connected to Redis")
        
        # Get all keys
        print("Scanning for keys...")
        keys = []
        async for key in redis.scan_iter("*"):
            keys.append(key)
        
        if not keys:
            print("✓ Redis is already empty - no keys found")
            await redis.close()
            return
        
        print(f"Found {len(keys)} key(s) to delete")
        
        # Delete all keys
        if keys:
            deleted = await redis.delete(*keys)
            print(f"✓ Deleted {deleted} key(s)")
        
        # Verify
        remaining_keys = []
        async for key in redis.scan_iter("*"):
            remaining_keys.append(key)
        
        if remaining_keys:
            print(f"⚠ Warning: {len(remaining_keys)} key(s) still remain")
        else:
            print("✓ Redis is now empty")
        
        await redis.close()
        print("✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        raise


if __name__ == "__main__":
    print("=" * 50)
    print("Redis Cache Cleaner")
    print("=" * 50)
    asyncio.run(clear_redis())

