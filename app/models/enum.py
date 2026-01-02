from enum import Enum


class RewardType(str, Enum):
    XP = "XP"
    CHECKOUT = "CHECKOUT"
    GOLD = "GOLD"


class Persona(str, Enum):
    NEW = "NEW"
    RETURNING = "RETURNING"
    POWER = "POWER"


class TransactionType(str, Enum):
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    ADJUSTMENT = "ADJUSTMENT"


class ReasonCode(str, Enum):
    XP_APPLIED = "XP_APPLIED"
    CASHBACK_GRANTED = "CASHBACK_GRANTED"
    GOLD_GRANTED = "GOLD_GRANTED"
    DAILY_CAC_EXCEEDED = "DAILY_CAC_EXCEEDED"
    CONFIG_BASED_DECISION = "CONFIG_BASED_DECISION"
