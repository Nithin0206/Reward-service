"""Tests for edge cases, boundary conditions, and invalid inputs."""

import pytest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from app.services.reward_engine import calculate_reward
from app.models.request import RewardRequest
from app.models.enum import RewardType, Persona, ReasonCode, TransactionType


@pytest.mark.asyncio
async def test_zero_amount_rejected():
    """Test that zero amount is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RewardRequest(
            txn_id="txn_001",
            user_id="user_001",
            merchant_id="merchant_001",
            amount=0.0,  # Zero amount
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )
    assert "amount" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_negative_amount_rejected():
    """Test that negative amounts are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RewardRequest(
            txn_id="txn_001",
            user_id="user_001",
            merchant_id="merchant_001",
            amount=-50.0,  # Negative amount
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )
    assert "amount" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_extremely_large_amount_rejected():
    """Test that extremely large amounts exceeding limit are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RewardRequest(
            txn_id="txn_001",
            user_id="user_001",
            merchant_id="merchant_001",
            amount=10_000_000.0,  # Exceeds 1 million limit
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )
    assert "amount" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_maximum_allowed_amount(mock_cache, mock_persona_service):
    """Test that maximum allowed amount (999,999) works correctly."""
    request = RewardRequest(
        txn_id="txn_max",
        user_id="user_max",
        merchant_id="merchant_001",
        amount=999_999.0,  # Just under 1 million limit
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    mock_cache.get = AsyncMock(side_effect=[
        None,  # idempotency
        "NEW",  # persona
        0,  # txn_count
        0   # CAC
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        # Should be capped at max_xp_per_txn
        assert response.xp == 500
        assert response.reward_value <= 500


@pytest.mark.asyncio
async def test_minimum_valid_amount(mock_cache, mock_persona_service):
    """Test minimum valid amount (0.01)."""
    request = RewardRequest(
        txn_id="txn_min",
        user_id="user_min",
        merchant_id="merchant_001",
        amount=0.01,  # Smallest valid amount
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    mock_cache.get = AsyncMock(side_effect=[
        None, None, 0, 0
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": True, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        assert response.xp >= 0  # Should give minimal XP
        assert response.reward_type == RewardType.XP


@pytest.mark.asyncio
async def test_empty_string_fields_rejected():
    """Test that empty string fields are rejected."""
    with pytest.raises(ValidationError):
        RewardRequest(
            txn_id="",  # Empty
            user_id="user_001",
            merchant_id="merchant_001",
            amount=100.0,
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )
    
    with pytest.raises(ValidationError):
        RewardRequest(
            txn_id="txn_001",
            user_id="",  # Empty
            merchant_id="merchant_001",
            amount=100.0,
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )


@pytest.mark.asyncio
async def test_whitespace_only_fields_rejected():
    """Test that whitespace-only fields are rejected."""
    with pytest.raises(ValidationError):
        RewardRequest(
            txn_id="   ",  # Whitespace only
            user_id="user_001",
            merchant_id="merchant_001",
            amount=100.0,
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )


@pytest.mark.asyncio
async def test_boundary_cac_limit_exactly_at_limit(mock_cache, mock_persona_service):
    """Test behavior when CAC is exactly at the limit."""
    request = RewardRequest(
        txn_id="txn_boundary",
        user_id="user_boundary",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    mock_cache.get = AsyncMock(side_effect=[
        None,  # idempotency
        "NEW",  # persona
        0,  # txn_count
        200  # CAC exactly at limit (200)
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        # At exact limit, should switch to XP
        assert response.reward_type == RewardType.XP
        assert response.reason_codes == [ReasonCode.DAILY_CAC_EXCEEDED]


@pytest.mark.asyncio
async def test_boundary_cac_one_below_limit(mock_cache, mock_persona_service):
    """Test behavior when CAC is one below the limit."""
    request = RewardRequest(
        txn_id="txn_boundary2",
        user_id="user_boundary2",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    mock_cache.get = AsyncMock(side_effect=[
        None,  # idempotency
        "NEW",  # persona
        0,  # txn_count
        199  # CAC one below limit (200)
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": False, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        # One below limit, should give cashback (capped at 1)
        assert response.reward_type == RewardType.CHECKOUT
        assert response.reward_value == 1


@pytest.mark.asyncio
async def test_persona_progression_boundary_exactly_3_transactions(mock_cache, mock_persona_service):
    """Test persona progression at exactly 3 transactions (NEW → RETURNING boundary)."""
    request = RewardRequest(
        txn_id="txn_boundary3",
        user_id="user_boundary3",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    # Transaction count = 2, after increment = 3 (should become RETURNING)
    mock_cache.get = AsyncMock(side_effect=[
        None,  # idempotency
        "NEW",  # persona
        2,  # txn_count (will become 3 after increment)
        0   # CAC
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": True, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        assert response.meta["persona"] == Persona.RETURNING.value


@pytest.mark.asyncio
async def test_persona_progression_boundary_exactly_10_transactions(mock_cache, mock_persona_service):
    """Test persona progression at exactly 10 transactions (RETURNING → POWER boundary)."""
    request = RewardRequest(
        txn_id="txn_boundary4",
        user_id="user_boundary4",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    # Transaction count = 9, after increment = 10 (should become POWER)
    mock_cache.get = AsyncMock(side_effect=[
        None,  # idempotency
        "RETURNING",  # persona
        9,  # txn_count (will become 10 after increment)
        0   # CAC
    ])
    
    with patch('app.services.reward_engine._get_cache', return_value=mock_cache), \
         patch('app.services.reward_engine.get_persona_service', return_value=mock_persona_service), \
         patch('app.services.reward_engine.CONFIG', {
             "xp_per_rupee": 1,
             "max_xp_per_txn": 500,
             "persona_multipliers": {"NEW": 1.5, "RETURNING": 1.2, "POWER": 1.0},
             "daily_cac_limit": {"NEW": 200, "RETURNING": 150, "POWER": 100},
             "gold_reward_value": 50,
             "feature_flags": {"prefer_xp": True, "prefer_gold": False},
             "policy_version": "v1",
             "cache": {"persona_ttl": 2592000, "cac_ttl": 86400, "idempotency_ttl": 86400}
         }):
        
        response = await calculate_reward(request)
        
        assert response.meta["persona"] == Persona.POWER.value


@pytest.mark.asyncio
async def test_very_long_string_ids():
    """Test handling of very long ID strings."""
    long_id = "x" * 1000  # 1000 character ID
    
    request = RewardRequest(
        txn_id=long_id,
        user_id="user_001",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    # Should accept long IDs
    assert request.txn_id == long_id


@pytest.mark.asyncio
async def test_special_characters_in_ids():
    """Test handling of special characters in IDs."""
    special_chars = "txn-001_@#$%_test"
    
    request = RewardRequest(
        txn_id=special_chars,
        user_id="user_001",
        merchant_id="merchant_001",
        amount=100.0,
        txn_type=TransactionType.PAYMENT,
        ts="2024-01-15T10:00:00"
    )
    
    # Should accept special characters
    assert request.txn_id == special_chars


@pytest.mark.asyncio
async def test_decimal_precision_amounts():
    """Test handling of amounts with various decimal precisions."""
    amounts = [
        100.1,      # 1 decimal
        100.12,     # 2 decimals
        100.123,    # 3 decimals
        100.1234,   # 4 decimals
    ]
    
    for amount in amounts:
        request = RewardRequest(
            txn_id="txn_001",
            user_id="user_001",
            merchant_id="merchant_001",
            amount=amount,
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )
        assert request.amount == amount


@pytest.mark.asyncio
async def test_invalid_transaction_type():
    """Test that invalid transaction types are rejected."""
    with pytest.raises(ValidationError):
        RewardRequest(
            txn_id="txn_001",
            user_id="user_001",
            merchant_id="merchant_001",
            amount=100.0,
            txn_type="INVALID_TYPE",
            ts="2024-01-15T10:00:00"
        )


@pytest.mark.asyncio
async def test_missing_required_fields():
    """Test that missing required fields are rejected."""
    with pytest.raises(ValidationError):
        RewardRequest(
            # Missing txn_id
            user_id="user_001",
            merchant_id="merchant_001",
            amount=100.0,
            txn_type=TransactionType.PAYMENT,
            ts="2024-01-15T10:00:00"
        )

