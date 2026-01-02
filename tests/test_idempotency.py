"""Tests for idempotency behavior."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.reward_engine import calculate_reward
from app.models.request import RewardRequest
from app.models.response import RewardResponse
from app.models.enum import RewardType


@pytest.mark.asyncio
async def test_duplicate_transaction_returns_cached_response(mock_cache, sample_request, mock_persona_service):
    """Test that duplicate transaction returns cached response with same decision_id."""
    cached_response = RewardResponse(
        decision_id="cached_decision_123",
        policy_version="v1",
        reward_type=RewardType.CHECKOUT,
        reward_value=150,
        xp=150,
        reason_codes=[],
        meta={"persona": "NEW", "daily_cac_used": 0, "daily_cac_limit": 200}
    )
    
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
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        first_response = await calculate_reward(sample_request)
        first_decision_id = first_response.decision_id
    
    mock_cache.get = AsyncMock(side_effect=[
        cached_response.model_dump(),
        None,
        None,
        None
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service):
        
        second_response = await calculate_reward(sample_request)
        
        assert second_response.decision_id == "cached_decision_123"
        assert second_response.reward_type == RewardType.CHECKOUT
        assert second_response.reward_value == 150


@pytest.mark.asyncio
async def test_idempotency_key_format(mock_cache, sample_request, mock_persona_service):
    """Test that idempotency key is correctly formatted."""
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
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        await calculate_reward(sample_request)
        
        calls = mock_cache.get.await_args_list
        idem_key = calls[0][0][0]  # First call, first argument
        expected_key = f"idem:{sample_request.txn_id}:{sample_request.user_id}:{sample_request.merchant_id}"
        assert idem_key == expected_key


@pytest.mark.asyncio
async def test_idempotency_response_cached(mock_cache, sample_request, mock_persona_service):
    """Test that response is cached after calculation."""
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
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(sample_request)
        
        import asyncio
        await asyncio.sleep(0.01)
        
        assert mock_cache.set.called, "Cache.set should be called to store response"
        assert response.decision_id is not None
        assert len(response.decision_id) > 0


@pytest.mark.asyncio
async def test_different_txn_id_creates_new_decision(mock_cache, sample_request, mock_persona_service):
    """Test that different transaction IDs create different decisions."""
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
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response1 = await calculate_reward(sample_request)
        decision_id1 = response1.decision_id
        
        sample_request.txn_id = "txn_different"
        response2 = await calculate_reward(sample_request)
        decision_id2 = response2.decision_id
        
        assert decision_id1 != decision_id2


@pytest.mark.asyncio
async def test_same_txn_different_user_not_idempotent(mock_cache, sample_request, mock_persona_service):
    """Test that same transaction ID but different user is not idempotent."""
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
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": True},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response1 = await calculate_reward(sample_request)
        decision_id1 = response1.decision_id
        
        sample_request.user_id = "user_different"
        response2 = await calculate_reward(sample_request)
        decision_id2 = response2.decision_id
        
        assert decision_id1 != decision_id2

