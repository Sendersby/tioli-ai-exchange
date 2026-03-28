"""Platform configuration loaded from environment variables."""

import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Platform identity
    platform_name: str = "TiOLi AGENTIS — The Agentic Exchange"
    version: str = "0.1.0"

    # Security
    secret_key: str = secrets.token_urlsafe(64)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Owner identity (3-factor auth)
    owner_email: str = "sendersby@tioli.onmicrosoft.com"
    owner_phone: str = ""  # Set via OWNER_PHONE env var
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

    # Module feature flags (Build Brief V2 — default false until owner enables)
    subscriptions_enabled: bool = False
    guild_enabled: bool = False
    pipelines_enabled: bool = False
    futures_enabled: bool = False
    training_data_enabled: bool = False
    treasury_enabled: bool = False
    compliance_service_enabled: bool = False
    benchmarking_enabled: bool = False
    intelligence_enabled: bool = False
    verticals_enabled: bool = False
    agenthub_enabled: bool = False
    agentvault_enabled: bool = False

    # Agentis Roadmap
    agentis_roadmap_enabled: bool = False
    agentis_roadmap_operator_visible: bool = False

    # Agentis Cooperative Bank feature flags — all default FALSE
    # Phase 1: CFI Level (build now, deploy on CBDA approval)
    agentis_compliance_enabled: bool = False      # Must be first — all others depend on it
    agentis_cfi_member_enabled: bool = False       # Member onboarding, KYC, mandates
    agentis_cfi_accounts_enabled: bool = False     # Share, Call, basic Savings accounts
    agentis_cfi_payments_enabled: bool = False     # Internal member-to-member transfers
    agentis_cfi_governance_enabled: bool = False   # Basic meeting management, voting
    agentis_phase0_wallet_enabled: bool = False    # Pre-banking wallet (FSP only)
    # Phase 2: Primary Co-op Bank (build later, deploy on SARB approval)
    agentis_pcb_deposits_enabled: bool = False     # Full deposit suite (FD, Notice, IR, MC)
    agentis_pcb_eft_enabled: bool = False          # External EFT payments
    agentis_pcb_treasury_enabled: bool = False     # Treasury snapshots, SARB reporting
    agentis_pcb_deposit_insurance_enabled: bool = False  # CoBIF levy, CoDI registration
    agentis_pcb_governance_enabled: bool = False   # AGM, dividends, special resolutions
    agentis_nca_lending_enabled: bool = False      # Full lending suite (OOD, EIL, BEL, RCF, ABA)
    agentis_cfi_lending_enabled: bool = False      # Basic member loans (PML, MEL)
    agentis_fsp_intermediary_enabled: bool = False # Insurance, pension, medical aid
    # Phase 3+: Advanced (build much later)
    agentis_fx_enabled: bool = False               # Foreign exchange, international payments
    agentis_casp_enabled: bool = False             # Crypto-denominated banking

    # Operator Hub
    operator_hub_enabled: bool = False
    github_client_id: str = ""
    github_client_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    oauth_redirect_base: str = "https://agentisexchange.com"

    # Debug
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
