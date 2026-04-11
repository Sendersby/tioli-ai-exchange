"""Pydantic validation models for API endpoints."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class VaultTier(str, Enum):
    CACHE = "AV-CACHE"
    LOCKER = "AV-LOCKER"
    CHAMBER = "AV-CHAMBER"
    CITADEL = "AV-CITADEL"


class VaultStoreRequest(BaseModel):
    vault_id: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=500)
    value: str = Field(min_length=1, max_length=100000)
    tier: VaultTier = VaultTier.CACHE


class GuildCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    operator_id: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    domains: Optional[List[str]] = None


class GuildJoinRequest(BaseModel):
    operator_id: str = Field(min_length=1, max_length=200)
    role: str = Field(default="member", max_length=50)


class FuturesCreateRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=200)
    operator_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=500)
    quantity: int = Field(gt=0, le=10000)
    price_per_unit: float = Field(gt=0, le=1000000)
    delivery_days: int = Field(gt=0, le=365)


class FuturesReserveRequest(BaseModel):
    buyer_id: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=10000)


class BadgeRequestModel(BaseModel):
    agent_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=5000)


class NotificationSendRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    template: Optional[str] = None
    vars: Optional[dict] = None
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=10000)


class WithdrawalRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=200)
    amount_zar: float = Field(gt=0, le=10000000)
    bank_account: str = Field(default="", max_length=50)
    bank_name: str = Field(default="", max_length=100)


class SelfDevProposeRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=200)
    type: str = Field(default="skill_enhancement", max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    code_diff: str = Field(default="", max_length=50000)


class FiatDepositRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=200)
    amount_zar: float = Field(gt=0, le=10000000)
    kyc_tier: int = Field(default=1, ge=1, le=5)


class FiatWithdrawRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=200)
    amount_agentis: float = Field(gt=0, le=10000000)
    kyc_tier: int = Field(default=1, ge=1, le=5)
