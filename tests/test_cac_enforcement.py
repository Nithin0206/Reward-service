"""Tests for CAC (Cashback Amount Claimed) cap enforcement."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.reward_engine import calculate_reward
from app.models.request import RewardRequest
from app.models.enum import RewardType, ReasonCode, Persona


@pytest.mark.asyncio
async def test_cac_limit_enforced_for_new_user(mock_cache, sample_request, mock_persona_service):
    """Test that CAC limit is enforced for NEW persona."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        1,
        199
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.CHECKOUT
        assert response.reward_value == 1  # Capped by remaining daily limit (200 - 199 = 1)
        assert response.meta["daily_cac_used"] == 199
        assert response.meta["daily_cac_limit"] == 200


@pytest.mark.asyncio
async def test_cac_limit_enforced_for_returning_user(mock_cache, sample_request, mock_persona_service):
    """Test that CAC limit is enforced for RETURNING persona."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "RETURNING",
        5,
        149
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.CHECKOUT
        assert response.reward_value == 1  # Capped by remaining daily limit (150 - 149 = 1)
        assert response.meta["daily_cac_used"] == 149
        assert response.meta["daily_cac_limit"] == 150


@pytest.mark.asyncio
async def test_cac_limit_enforced_for_power_user(mock_cache, sample_request, mock_persona_service):
    """Test that CAC limit is enforced for POWER persona.
    
    Note: With prefer_gold=true, POWER users get GOLD, so we disable it for this test.
    """
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "POWER",
        15,
        99
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.CHECKOUT
        assert response.reward_value == 1  # Capped by remaining daily limit (100 - 99 = 1)
        assert response.meta["daily_cac_used"] == 99
        assert response.meta["daily_cac_limit"] == 100


@pytest.mark.asyncio
async def test_cac_exceeded_switches_to_xp(mock_cache, sample_request, mock_persona_service):
    """Test that when CAC limit is exceeded, reward switches to XP."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        1,
        200
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.XP
        assert response.reason_codes == [ReasonCode.DAILY_CAC_EXCEEDED]
        assert response.meta["daily_cac_used"] == 200
        assert response.meta["daily_cac_limit"] == 200


@pytest.mark.asyncio
async def test_cac_cumulative_tracking(mock_cache, sample_request, mock_persona_service):
    """Test that CAC is tracked cumulatively across transactions."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        0,
        0
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response1 = await calculate_reward(sample_request)
        first_cac = response1.reward_value
    
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        1,
        first_cac
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response2 = await calculate_reward(sample_request)
        
        # First transaction: 100 * 10% = 10 rupees cashback
        # Second transaction: also 10 rupees (both capped by 10% rule)
        assert response2.reward_value == 10
        assert response2.meta["daily_cac_used"] == first_cac


@pytest.mark.asyncio
async def test_cac_capped_by_xp_calculation(mock_cache, sample_request, mock_persona_service):
    """Test that cashback is capped by calculated XP value."""
    sample_request.amount = 50.0
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        1,
        0
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.CHECKOUT
        # XP = 50 * 1 * 1.5 = 75, but cashback capped at 50 * 10% = 5 rupees
        assert response.reward_value == 5
        assert response.xp == 75


@pytest.mark.asyncio
async def test_cac_daily_reset_simulation(mock_cache, sample_request, mock_persona_service):
    """Test that CAC resets daily (simulated by different date keys)."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        0,
        0
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }), \
         patch('app.services.reward_engine._get_today_string', return_value="2024-01-15"):
        
        response1 = await calculate_reward(sample_request)
        first_cac = response1.reward_value
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "max_cashback_percentage": 10,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }), \
         patch('app.services.reward_engine._get_today_string', return_value="2024-01-16"):
        
        mock_cache.get = AsyncMock(side_effect=[
            None,
            "NEW",
            1,
            None
        ])
        
        response2 = await calculate_reward(sample_request)
        
        # New day, so CAC resets. 100 * 10% = 10 rupees cashback
        assert response2.reward_value == 10
        assert response2.meta["daily_cac_used"] == 0

