from pydantic import BaseModel
from typing import List, Dict, Any
from app.models.enum import RewardType, ReasonCode

class RewardResponse(BaseModel):
    decision_id: str
    policy_version: str
    reward_type: RewardType
    reward_value: int
    xp: int
    reason_codes: List[ReasonCode]
    meta: Dict[str, Any]
