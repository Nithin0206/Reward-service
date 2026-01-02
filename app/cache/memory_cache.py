"""Async in-memory cache implementation."""

import time
import asyncio
from typing import Any, Optional, Dict


class MemoryCache:
    """Async thread-safe in-memory cache using asyncio locks."""
    
    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize async memory cache.
        
        Args:
            max_size: Maximum number of items to cache (None for unlimited)
        """
        self.store: Dict[str, tuple] = {}
        self.lock = asyncio.Lock()
        self.max_size = max_size
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        async with self.lock:
            val = self.store.get(key)
            if not val:
                return None
            data, expiry = val
            if expiry and expiry < time.time():
                del self.store[key]
                return None
            return data
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)
            
        Returns:
            True if successful
        """
        async with self.lock:
            if self.max_size and len(self.store) >= self.max_size and key not in self.store:
                expired_key = None
                for k, (_, expiry) in self.store.items():
                    if expiry and expiry < time.time():
                        expired_key = k
                        break
                
                if expired_key:
                    del self.store[expired_key]
                else:
                    first_key = next(iter(self.store))
                    del self.store[first_key]
            
            expiry = time.time() + ttl if ttl else None
            self.store[key] = (value, expiry)
            return True
    
    async def mget(self, keys: list) -> list:
        """
        Get multiple values at once.
        
        Args:
            keys: List of cache keys
            
        Returns:
            List of cached values (None for missing keys)
        """
        async with self.lock:
            results = []
            for key in keys:
                val = self.store.get(key)
                if not val:
                    results.append(None)
                else:
                    data, expiry = val
                    if expiry and expiry < time.time():
                        del self.store[key]
                        results.append(None)
                    else:
                        results.append(data)
            return results
    
    async def mset(self, key_value_pairs: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values at once.
        
        Args:
            key_value_pairs: Dictionary of key-value pairs
            ttl: Optional TTL for all keys
            
        Returns:
            True if successful
        """
        async with self.lock:
            expiry = time.time() + ttl if ttl else None
            
            for key, value in key_value_pairs.items():
                if self.max_size and len(self.store) >= self.max_size and key not in self.store:
                    expired_key = None
                    for k, (_, exp) in self.store.items():
                        if exp and exp < time.time():
                            expired_key = k
                            break
                    
                    if expired_key:
                        del self.store[expired_key]
                    else:
                        first_key = next(iter(self.store))
                        del self.store[first_key]
                
                self.store[key] = (value, expiry)
            
            return True
