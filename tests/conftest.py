"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import date
from app.models.request import RewardRequest
from app.models.enum import TransactionType
from app.cache.memory_cache import MemoryCache
from app.services.persona_service import PersonaService


@pytest.fixture
def mock_cache():
    """Create a mock cache instance."""
    cache = AsyncMock(spec=MemoryCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.mget = AsyncMock(return_value=[None, None, None, None])
    cache.mset = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def sample_request():
    """Create a sample reward request."""
    return RewardRequest(
        txn_id="txn_test_001",
        user_id="user_test_001",
        merchant_id="merchant_test_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )


@pytest.fixture
def mock_persona_service():
    """Create a mock persona service."""
    service = MagicMock(spec=PersonaService)
    service.get_persona = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "xp_per_rupee": 1,
        "max_xp_per_txn": 500,
        "persona_multipliers": {
            "NEW": 1.5,
            "RETURNING": 1.2,
            "POWER": 1.0
        },
        "daily_cac_limit": {
            "NEW": 200,
            "RETURNING": 150,
            "POWER": 100
        },
        "gold_reward_value": 50,
        "feature_flags": {
            "prefer_xp": False,
            "prefer_gold": True,
            "cooldown_enabled": True
        },
        "policy_version": "v1",
        "cache": {
            "default_ttl": 86400,
            "idempotency_ttl": 86400,
            "persona_ttl": 2592000,
            "cac_ttl": 86400
        }
    }


@pytest.fixture
def today_string():
    """Get today's date string."""
    return str(date.today())


@pytest.fixture(autouse=True)
def cleanup_background_tasks(event_loop):
    """Clean up background tasks after each test to prevent warnings."""
    yield
    # Clean up any pending tasks
    try:
        if event_loop and not event_loop.is_closed():
            pending = [task for task in asyncio.all_tasks(event_loop) if not task.done()]
            if pending:
                # Cancel remaining tasks
                for task in pending:
                    if not task.done():
                        task.cancel()
                # Wait briefly for cancellations
                if pending:
                    event_loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
    except Exception:
        pass  # Ignore errors during cleanup

