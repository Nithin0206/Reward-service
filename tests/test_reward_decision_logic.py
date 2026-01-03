"""Tests for reward decision logic."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.reward_engine import calculate_reward
from app.models.request import RewardRequest
from app.models.enum import RewardType, Persona, ReasonCode, TransactionType
from app.models.response import RewardResponse


@pytest.mark.asyncio
async def test_new_user_gets_checkout_reward(mock_cache, sample_request, mock_persona_service):
    """Test that a new user gets CHECKOUT reward when CAC is within limit."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        None,
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
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.CHECKOUT
        assert response.reason_codes == [ReasonCode.CASHBACK_GRANTED]
        assert response.meta["persona"] == Persona.NEW.value
        assert response.xp == 150
        assert response.reward_value == 10  # 100 * 10% = 10 rupees (capped by percentage)


@pytest.mark.asyncio
async def test_cac_exceeded_gets_xp(mock_cache, sample_request, mock_persona_service):
    """Test that when CAC limit is exceeded, user gets XP reward."""
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
        assert response.xp == 150
        assert response.reward_value == 150
        assert response.meta["daily_cac_limit"] == 200


@pytest.mark.asyncio
async def test_power_user_gets_gold_when_prefer_gold_enabled(mock_cache, sample_request, mock_persona_service):
    """Test that POWER user gets GOLD when prefer_gold is enabled and CAC within limit."""
    sample_request.amount = 200.0
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "POWER",
        15,
        50
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
        
        assert response.reward_type == RewardType.GOLD
        assert response.reason_codes == [ReasonCode.GOLD_GRANTED]
        assert response.reward_value == 50
        assert response.meta["persona"] == Persona.POWER.value


@pytest.mark.asyncio
async def test_prefer_xp_gets_xp_reward(mock_cache, sample_request, mock_persona_service):
    """Test that when prefer_xp is enabled, user gets XP reward."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        None,
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
             "feature_flags": {"prefer_xp": True, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        assert response.reward_type == RewardType.XP
        assert response.reason_codes == [ReasonCode.XP_APPLIED]
        assert response.xp == 150
        assert response.reward_value == 150


@pytest.mark.asyncio
async def test_cashback_capped_by_remaining_limit(mock_cache, sample_request, mock_persona_service):
    """Test that cashback is capped by remaining daily CAC limit."""
    sample_request.amount = 50.0
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
        assert response.xp == 75


@pytest.mark.asyncio
async def test_persona_progression_new_to_returning(mock_cache, sample_request, mock_persona_service):
    """Test persona progression from NEW to RETURNING after 3 transactions."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "NEW",
        2,
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
        
        assert response.meta["persona"] == Persona.RETURNING.value
        assert mock_cache.set.call_count >= 1


@pytest.mark.asyncio
async def test_persona_progression_returning_to_power(mock_cache, sample_request, mock_persona_service):
    """Test persona progression from RETURNING to POWER after 10 transactions."""
    mock_cache.get = AsyncMock(side_effect=[
        None,
        "RETURNING",
        9,
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
        
        assert response.meta["persona"] == Persona.POWER.value


@pytest.mark.asyncio
async def test_xp_calculation_with_different_personas(mock_cache, sample_request, mock_persona_service):
    """Test XP calculation with different persona multipliers."""
    test_cases = [
        ("NEW", 1, 150),
        ("RETURNING", 5, 120),
        ("POWER", 15, 100)
    ]
    
    for persona, txn_count, expected_xp in test_cases:
        mock_cache.get = AsyncMock(side_effect=[
            None,
            persona,
            txn_count,
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
                 "feature_flags": {"prefer_xp": True, "prefer_gold": False},
                 "policy_version": "v1",
                 "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
             }):
            
            response = await calculate_reward(sample_request)
            assert response.xp == expected_xp, f"Failed for persona {persona}"


@pytest.mark.asyncio
async def test_xp_capped_at_max_per_txn(mock_cache, mock_persona_service):
    """Test that XP is capped at max_xp_per_txn."""
    large_request = RewardRequest(
        txn_id="txn_large",
        user_id="user_large",
        merchant_id="merchant_001",
        amount=1000.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
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
             "feature_flags": {"prefer_xp": True, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(large_request)
        
        assert response.xp == 500
        assert response.reward_value == 500

