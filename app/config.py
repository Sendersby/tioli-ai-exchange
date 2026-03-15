"""Platform configuration loaded from environment variables."""

import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Platform identity
    platform_name: str = "TiOLi AI Transact Exchange"
    version: str = "0.1.0"

    # Security
    secret_key: str = secrets.token_urlsafe(64)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Owner identity (3-factor auth)
    owner_email: str = "sendersby@tioli.onmicrosoft.com"
    owner_phone: str = "+270827090435"
    owner_cli_token: str = secrets.token_urlsafe(32)

    # Database
    database_url: str = "sqlite+aiosqlite:///./tioli_exchange.db"

    # Fee structure
    founder_commission_rate: float = 0.12  # 12% default (range: 10-15%)
    charity_fee_rate: float = 0.10  # 10% to charitable causes
    min_commission_rate: float = 0.10
    max_commission_rate: float = 0.15

    # Financial governance
    expense_profitability_multiplier: float = 10.0  # 10x rule
    security_expense_multiplier: float = 3.0  # 3x exception for security

    # AgentBroker feature flag (Phase 1: false, Phase 2: true)
    agentbroker_enabled: bool = False

    # Debug
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
