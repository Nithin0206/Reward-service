"""Async Redis cache implementation with error handling and optimizations."""

import json
import time
from typing import Any, Optional, Dict, List, Tuple
import aioredis
from aioredis import Redis
from aioredis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    ResponseError,
    AuthenticationError,
    BusyLoadingError
)


class RedisCache:
    """
    Async Redis cache implementation with connection pooling, pipeline support,
    and optimized error handling.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        max_connections: int = 50,
        socket_connect_timeout: int = 5,
        socket_timeout: int = 5,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30
    ):
        """
        Initialize async Redis cache client with connection pooling.
        
        Args:
            host: Redis host
            port: Redis port
            max_connections: Maximum number of connections in the pool
            socket_connect_timeout: Timeout for socket connection
            socket_timeout: Timeout for socket operations
            retry_on_timeout: Whether to retry on timeout
            health_check_interval: Interval for health checks (seconds)
        """
        self.host = host
        self.port = port
        self._redis: Optional[Redis] = None
        self._connection_url = f"redis://{host}:{port}"
        self._max_connections = max_connections
        self._socket_connect_timeout = socket_connect_timeout
        self._socket_timeout = socket_timeout
        self._retry_on_timeout = retry_on_timeout
        self._health_check_interval = health_check_interval
        
        self._last_health_check = 0
        self._is_healthy = True
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        
        self._serialization_cache: Dict[str, Tuple[str, float]] = {}
        self._serialization_cache_ttl = 60
        
    async def _initialize(self) -> None:
        """Initialize Redis connection pool."""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    self._connection_url,
                    max_connections=self._max_connections,
                    socket_connect_timeout=self._socket_connect_timeout,
                    socket_timeout=self._socket_timeout,
                    retry_on_timeout=self._retry_on_timeout,
                    decode_responses=True
                )
                # Test initial connection
                await self._redis.ping()
                self._is_healthy = True
            except Exception as e:
                raise ConnectionError(f"Failed to connect to Redis at {self.host}:{self.port}: {str(e)}")
    
    async def _check_health_on_error(self) -> bool:
        """Check health only when errors occur."""
        current_time = time.time()
        
        if current_time - self._last_health_check < self._health_check_interval:
            return self._is_healthy
        
        self._last_health_check = current_time
        
        try:
            if self._redis:
                await self._redis.ping()
                self._is_healthy = True
                self._consecutive_errors = 0
                return True
        except Exception:
            self._is_healthy = False
            self._consecutive_errors += 1
        
        return self._is_healthy
    
    def _handle_redis_error(self, error: Exception, operation: str) -> None:
        """Handle Redis errors."""
        if isinstance(error, (RedisConnectionError, RedisTimeoutError)):
            self._is_healthy = False
            print(f"Redis connection error during {operation}: {str(error)}")
        elif isinstance(error, BusyLoadingError):
            print(f"Redis is loading data during {operation}: {str(error)}")
        elif isinstance(error, ResponseError):
            print(f"Redis response error during {operation}: {str(error)}")
        else:
            print(f"Redis error during {operation}: {str(error)}")
    
    async def _serialize_value(self, value: Any, key: str) -> str:
        """Serialize value with caching."""
        # Always JSON-encode values, including strings, for consistency
        current_time = time.time()
        if key in self._serialization_cache:
            cached_serialized, cache_time = self._serialization_cache[key]
            if current_time - cache_time < self._serialization_cache_ttl:
                return cached_serialized
        
        try:
            serialized = json.dumps(value)
            self._serialization_cache[key] = (serialized, current_time)
            return serialized
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize value for key {key}: {str(e)}")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with error handling.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or error
        """
        await self._initialize()
        
        if not self._redis:
            return None
        
        if self._consecutive_errors >= self._max_consecutive_errors:
            if not await self._check_health_on_error():
                return None
        
        try:
            data = await self._redis.get(key)
            if data is None:
                return None
            
            if isinstance(data, str):
                try:
                    # Try to parse as JSON first
                    return json.loads(data)
                except json.JSONDecodeError:
                    # If JSON parsing fails, it might be a plain string value
                    # (from old data stored before JSON encoding was enforced)
                    # Return as plain string for backward compatibility
                    return data
            
            return data
            
        except (RedisConnectionError, RedisTimeoutError) as e:
            self._handle_redis_error(e, 'get')
            self._consecutive_errors += 1
            await self._check_health_on_error()
            return None
            
        except (ResponseError, BusyLoadingError) as e:
            self._handle_redis_error(e, 'get')
            return None
            
        except json.JSONDecodeError:
            print(f"JSON decode error for key {key}")
            return None
            
        except Exception as e:
            self._handle_redis_error(e, 'get')
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """
        Set value in cache with TTL and error handling.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        await self._initialize()
        
        if not self._redis:
            return False
        
        if self._consecutive_errors >= self._max_consecutive_errors:
            if not await self._check_health_on_error():
                return False
        
        try:
            serialized = await self._serialize_value(value, key)
            await self._redis.setex(key, ttl, serialized)
            self._consecutive_errors = 0
            return True
            
        except (RedisConnectionError, RedisTimeoutError) as e:
            self._handle_redis_error(e, 'set')
            self._consecutive_errors += 1
            await self._check_health_on_error()
            return False
            
        except (ResponseError, BusyLoadingError) as e:
            self._handle_redis_error(e, 'set')
            return False
            
        except (TypeError, ValueError) as e:
            print(f"Serialization error for key {key}: {str(e)}")
            return False
            
        except Exception as e:
            self._handle_redis_error(e, 'set')
            return False
    
    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values at once."""
        await self._initialize()
        
        if not self._redis or not keys:
            return [None] * len(keys)
        
        try:
            values = await self._redis.mget(keys)
            results = []
            
            for value in values:
                if value is None:
                    results.append(None)
                elif isinstance(value, str):
                    try:
                        results.append(json.loads(value))
                    except json.JSONDecodeError:
                        # If JSON parsing fails, return as plain string for backward compatibility
                        results.append(value)
                else:
                    results.append(value)
            
            return results
            
        except Exception as e:
            self._handle_redis_error(e, 'mget')
            return [None] * len(keys)
    
    async def mset(self, key_value_pairs: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values at once."""
        await self._initialize()
        
        if not self._redis or not key_value_pairs:
            return False
        
        try:
            serialized_pairs = {}
            for key, value in key_value_pairs.items():
                serialized = await self._serialize_value(value, key)
                serialized_pairs[key] = serialized
            
            pipe = self._redis.pipeline()
            pipe.mset(serialized_pairs)
            
            if ttl:
                for key in key_value_pairs.keys():
                    pipe.expire(key, ttl)
            
            await pipe.execute()
            self._consecutive_errors = 0
            return True
            
        except Exception as e:
            self._handle_redis_error(e, 'mset')
            return False
    
    async def pipeline(self):
        """Get a Redis pipeline for batch operations."""
        await self._initialize()
        if self._redis:
            return self._redis.pipeline()
        raise ConnectionError("Redis not initialized")
    
    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            await self._initialize()
            if self._redis:
                await self._redis.ping()
                return True
        except Exception:
            pass
        return False
    
    async def close(self) -> None:
        """Close Redis connection."""
        try:
            if self._redis:
                await self._redis.close()
                self._redis = None
        except Exception:
            pass
        finally:
            self._is_healthy = False
