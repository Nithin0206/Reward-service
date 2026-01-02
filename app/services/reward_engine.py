import logging
logging.basicConfig(level=logging.DEBUG)



import uuid
import asyncio
from datetime import date
from typing import Dict, Any, Optional, Tuple
from app.utils.config_loader import CONFIG
from app.cache.cache_manager import get_cache
from app.models.response import RewardResponse
from app.models.request import RewardRequest
from app.models.enum import RewardType, Persona, ReasonCode

_cache: Optional[Any] = None
_config_validation_cache: Dict[str, bool] = {}
_today_cache: Optional[Tuple[str, date]] = None
_today_lock = asyncio.Lock()

async def _get_cache():
    """Get or initialize async cache instance."""
    global _cache
    if _cache is None:
        _cache = await get_cache()
    return _cache


async def _get_today_string() -> str:
    """Get today's date string with caching."""
    global _today_cache
    
    async with _today_lock:
        today = date.today()
        if _today_cache is None or _today_cache[1] != today:
            _today_cache = (str(today), today)
        return _today_cache[0]


def _validate_config_cached(cfg: Dict[str, Any], persona: str) -> None:
    """Validate config with caching."""
    cache_key = f"config_valid_{persona}"
    
    if cache_key in _config_validation_cache:
        if not _config_validation_cache[cache_key]:
            raise ValueError(f"Config validation failed for persona: {persona}")
        return
    
    required_keys = ["xp_per_rupee", "max_xp_per_txn", "persona_multipliers", 
                     "daily_cac_limit", "feature_flags", "policy_version"]
    for key in required_keys:
        if key not in cfg:
            _config_validation_cache[cache_key] = False
            raise ValueError(f"Missing required config key: {key}")
    
    if persona not in cfg["persona_multipliers"]:
        _config_validation_cache[cache_key] = False
        raise ValueError(f"Persona '{persona}' not found in persona_multipliers config")
    
    if persona not in cfg["daily_cac_limit"]:
        _config_validation_cache[cache_key] = False
        raise ValueError(f"Persona '{persona}' not found in daily_cac_limit config")
    
    _config_validation_cache[cache_key] = True


def _get_valid_persona(persona_value: Any) -> str:
    """Validate and return a valid persona value."""
    if isinstance(persona_value, str):
        valid_personas = [p.value for p in Persona]
        if persona_value in valid_personas:
            return persona_value
    return Persona.NEW.value


def _get_cached_response(cached: Any) -> RewardResponse:
    """Convert cached data to RewardResponse object."""
    if isinstance(cached, dict):
        return RewardResponse(**cached)
    elif isinstance(cached, RewardResponse):
        return cached
    else:
        raise ValueError(f"Unexpected cached data type: {type(cached)}")


async def calculate_reward(req: RewardRequest) -> RewardResponse:
    """
    Calculate reward for a transaction request.
    
    Args:
        req: RewardRequest containing transaction details
        
    Returns:
        RewardResponse with reward decision
        
    Raises:
        ValueError: If input validation fails
        RuntimeError: If reward calculation fails
    """
    try:
        cache = await _get_cache()
        today = await _get_today_string()
        
        idem_key = f"idem:{req.txn_id}:{req.user_id}:{req.merchant_id}"
        persona_key = f"persona:{req.user_id}"
        txn_count_key = f"txn_count:{req.user_id}"
        cac_key = f"cac:{req.user_id}:{today}"
        
        idem_task = cache.get(idem_key)
        persona_task = cache.get(persona_key)
        txn_count_task = cache.get(txn_count_key)
        cac_task = cache.get(cac_key)
        
        cached_response, persona_raw, txn_count_raw, current_cac_raw = await asyncio.gather(
            idem_task,
            persona_task,
            txn_count_task,
            cac_task,
            return_exceptions=True
        )
        
        if isinstance(cached_response, Exception):
            cached_response = None
        if cached_response:
            return _get_cached_response(cached_response)
        
        if isinstance(persona_raw, Exception):
            persona_raw = None
        persona = _get_valid_persona(persona_raw) if persona_raw else Persona.NEW.value
        
        if isinstance(txn_count_raw, Exception):
            txn_count_raw = 0
        # Handle transaction count - support int, float, and string numbers (for backward compatibility)
        if isinstance(txn_count_raw, (int, float)):
            txn_count = int(txn_count_raw)
        elif isinstance(txn_count_raw, str):
            try:
                txn_count = int(float(txn_count_raw))  # Handle both "5" and "5.0"
            except (ValueError, TypeError):
                txn_count = 0
        else:
            txn_count = 0
        txn_count += 1
        
        if persona == Persona.NEW.value and txn_count >= 3:
            persona = Persona.RETURNING.value
        elif persona == Persona.RETURNING.value and txn_count >= 10:
            persona = Persona.POWER.value
        
        if isinstance(current_cac_raw, Exception):
            current_cac_raw = None
        # Handle CAC value - support int, float, and string numbers (for backward compatibility)
        if isinstance(current_cac_raw, (int, float)):
            current_cac = max(0, int(current_cac_raw))
        elif isinstance(current_cac_raw, str):
            try:
                current_cac = max(0, int(float(current_cac_raw)))  # Handle both "100" and "100.0"
            except (ValueError, TypeError):
                current_cac = 0
        else:
            current_cac = 0
        
        cfg = CONFIG
        _validate_config_cached(cfg, persona)
        
        cache_config = cfg.get("cache", {})
        persona_ttl = cache_config.get("persona_ttl", 2592000)
        cac_ttl = cache_config.get("cac_ttl", 86400)
        idempotency_ttl = cache_config.get("idempotency_ttl", 86400)
        
        xp_per_rupee = cfg.get("xp_per_rupee", 1)
        max_xp = cfg.get("max_xp_per_txn", 500)
        multiplier = cfg["persona_multipliers"][persona]
        daily_limit = int(cfg["daily_cac_limit"][persona])
        feature_flags = cfg.get("feature_flags", {})
        policy_version = cfg.get("policy_version", "v1")
        if not isinstance(xp_per_rupee, (int, float)) or xp_per_rupee < 0:
            raise ValueError("xp_per_rupee must be a non-negative number")
        if not isinstance(multiplier, (int, float)) or multiplier < 0:
            raise ValueError(f"persona_multipliers[{persona}] must be a non-negative number")
        if not isinstance(max_xp, (int, float)) or max_xp < 0:
            raise ValueError("max_xp_per_txn must be a non-negative number")
        if daily_limit < 0:
            raise ValueError(f"daily_cac_limit[{persona}] must be a non-negative number")
        
        xp = int(req.amount * xp_per_rupee * multiplier)
        xp = min(xp, int(max_xp))
        xp = max(0, xp)
        if current_cac >= daily_limit:
            reward_type = RewardType.XP
            reward_value = xp
            reason = ReasonCode.DAILY_CAC_EXCEEDED
        elif feature_flags.get("prefer_gold") and persona == Persona.POWER.value:
            reward_type = RewardType.GOLD
            gold_value = cfg.get("gold_reward_value", 50)
            if not isinstance(gold_value, (int, float)) or gold_value < 0:
                raise ValueError("gold_reward_value must be a non-negative number")
            reward_value = int(gold_value)
            reason = ReasonCode.GOLD_GRANTED
        elif feature_flags.get("prefer_xp"):
            reward_type = RewardType.XP
            reward_value = xp
            reason = ReasonCode.XP_APPLIED
        else:
            reward_type = RewardType.CHECKOUT
            reward_value = min(max(0, daily_limit - current_cac), xp)
            reason = ReasonCode.CASHBACK_GRANTED
        
        response = RewardResponse(
            decision_id=str(uuid.uuid4()),
            policy_version=policy_version,
            reward_type=reward_type,
            reward_value=reward_value,
            xp=xp,
            reason_codes=[reason],
            meta={
                "persona": persona,
                "daily_cac_used": current_cac,
                "daily_cac_limit": daily_limit
            }
        )
        
        cache_writes = []
        
        cache_writes.append(cache.set(persona_key, persona, ttl=persona_ttl))
        cache_writes.append(cache.set(txn_count_key, txn_count, ttl=persona_ttl))
        
        # Update CAC for all reward types to track daily limit usage
        # CAC tracks the equivalent cashback value consumed, regardless of reward type
        # This ensures the daily limit check (line 189) works correctly
        new_cac = current_cac + reward_value
        cache_writes.append(cache.set(cac_key, new_cac, ttl=cac_ttl))
        
        cache_writes.append(cache.set(idem_key, response.model_dump(), ttl=idempotency_ttl))
        
        if cache_writes:
            async def _write_cache():
                try:
                    await asyncio.gather(*cache_writes, return_exceptions=True)
                except Exception:
                    pass
            
            asyncio.create_task(_write_cache())
        
        return response
        
    except ValueError as e:
        raise ValueError(f"Invalid input or configuration: {str(e)}")
    except KeyError as e:
        raise ValueError(f"Missing configuration key: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Reward decision failed: {str(e)}")
