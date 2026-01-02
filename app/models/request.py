from pydantic import BaseModel, Field, validator
from datetime import datetime

class RewardRequest(BaseModel):
    txn_id: str = Field(..., min_length=1, description="Transaction ID")
    user_id: str = Field(..., min_length=1, description="User ID")
    merchant_id: str = Field(..., min_length=1, description="Merchant ID")
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    txn_type: str = Field(..., min_length=1, description="Transaction type")
    ts: str = Field(..., description="Timestamp")
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 1000000:  # Reasonable upper limit
            raise ValueError('Amount exceeds maximum allowed value')
        return v
    
    @validator('txn_id', 'user_id', 'merchant_id', 'txn_type')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
