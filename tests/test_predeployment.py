"""Tests for pre-deployment review remediation items."""

import pytest
from app.operators.models import (
    OperatorTier, KYCLevel, TIER_COMMISSION_RATES, KYC_TRANSACTION_LIMITS,
)
from app.security.transaction_safety import InputValidator
from app.mcp.server import TiOLiMCPServer
from app.legal.documents import PlatformLegalDocuments
from app.infrastructure.disaster_recovery import DisasterRecoveryConfig, IncidentResponsePlan


class TestOperatorPrincipalModel:
    """FP2: Agents must have a registered operator as legal principal."""

    def test_tier_commission_rates(self):
        assert TIER_COMMISSION_RATES[OperatorTier.EARLY_ADOPTER] == 0.12
        assert TIER_COMMISSION_RATES[OperatorTier.VOLUME] == 0.08
        assert TIER_COMMISSION_RATES[OperatorTier.ENTERPRISE] == 0.05

    def test_tiered_compression(self):
        """FP3: Rates compress as operators scale."""
        rates = list(TIER_COMMISSION_RATES.values())
        assert rates == sorted(rates, reverse=True)

    def test_kyc_levels(self):
        assert KYCLevel.NONE == 0
        assert KYCLevel.BASIC == 1
        assert KYCLevel.ENHANCED == 2
        assert KYCLevel.FULL == 3

    def test_kyc_transaction_limits_scale(self):
        assert KYC_TRANSACTION_LIMITS[KYCLevel.NONE] == 0
        assert KYC_TRANSACTION_LIMITS[KYCLevel.BASIC] < KYC_TRANSACTION_LIMITS[KYCLevel.ENHANCED]
        assert KYC_TRANSACTION_LIMITS[KYCLevel.ENHANCED] < KYC_TRANSACTION_LIMITS[KYCLevel.FULL]


class TestInputValidation:
    """Section 7.2: Strict allowlist input validation."""

    def test_valid_amount(self):
        assert InputValidator.validate_amount(100.0) == 100.0

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            InputValidator.validate_amount(-50.0)

    def test_excessive_amount_rejected(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            InputValidator.validate_amount(2_000_000_000)

    def test_valid_currency(self):
        assert InputValidator.validate_currency("TIOLI") == "TIOLI"
        assert InputValidator.validate_currency("btc") == "BTC"

    def test_invalid_currency_rejected(self):
        with pytest.raises(ValueError):
            InputValidator.validate_currency("a")  # Too short
        with pytest.raises(ValueError):
            InputValidator.validate_currency("invalid-symbol!")

    def test_valid_email(self):
        assert InputValidator.validate_email("test@example.com") == "test@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValueError):
            InputValidator.validate_email("not-an-email")

    def test_side_validation(self):
        assert InputValidator.validate_side("buy") == "buy"
        assert InputValidator.validate_side("SELL") == "sell"
        with pytest.raises(ValueError):
            InputValidator.validate_side("hold")

    def test_string_length_limit(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            InputValidator.validate_string("x" * 300, "name", max_length=255)


class TestMCPServer:
    """Section 10.3: MCP integration — most important opportunity."""

    def test_server_info(self):
        server = TiOLiMCPServer()
        info = server.get_server_info()
        assert info["name"] == "tioli-ai-transact-exchange"
        assert "version" in info

    def test_tools_defined(self):
        server = TiOLiMCPServer()
        tools = server.get_tools()
        assert len(tools) >= 10
        names = [t["name"] for t in tools]
        assert "tioli_register" in names
        assert "tioli_trade" in names
        assert "tioli_convert" in names
        assert "tioli_lend" in names
        assert "tioli_portfolio" in names

    def test_manifest_structure(self):
        server = TiOLiMCPServer()
        manifest = server.get_mcp_manifest()
        assert "server" in manifest
        assert "tools" in manifest
        assert "capabilities" in manifest
        assert manifest["capabilities"]["tools"] is True

    def test_tool_schemas(self):
        server = TiOLiMCPServer()
        tools = server.get_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool


class TestLegalDocuments:
    """Critical item 7: ToS, Privacy Notice, SLA must exist."""

    def test_tos_exists(self):
        tos = PlatformLegalDocuments.get_terms_of_service()
        assert tos["document"] == "Terms of Service"
        assert "sections" in tos
        assert "governing_law" in tos

    def test_tos_has_dispute_resolution(self):
        tos = PlatformLegalDocuments.get_terms_of_service()
        assert "8_dispute_resolution" in tos["sections"]

    def test_tos_has_prohibited_uses(self):
        tos = PlatformLegalDocuments.get_terms_of_service()
        prohibited = tos["sections"]["5_prohibited_uses"]
        assert len(prohibited) >= 5

    def test_privacy_notice_popia_compliant(self):
        pn = PlatformLegalDocuments.get_privacy_notice()
        assert pn["document"] == "Privacy Notice"
        assert "information_officer" in pn
        assert "6_data_subject_rights" in pn["sections"]
        assert "8_breach_notification" in pn["sections"]

    def test_privacy_has_retention_policy(self):
        pn = PlatformLegalDocuments.get_privacy_notice()
        assert "4_data_retention" in pn["sections"]

    def test_sla_exists(self):
        sla = PlatformLegalDocuments.get_sla()
        assert sla["document"] == "Service Level Agreement"
        assert "uptime_commitment" in sla["sections"]
        assert sla["sections"]["uptime_commitment"]["target"] == "99.5%"

    def test_api_versioning_policy(self):
        policy = PlatformLegalDocuments.get_api_versioning_policy()
        assert policy["current_api_version"] == "v1"
        assert "deprecation_process" in policy["sections"]


class TestDisasterRecovery:
    """Critical item 6: DR must be defined and tested."""

    def test_rto_rpo_defined(self):
        assert DisasterRecoveryConfig.RTO_TARGET_MINUTES == 30
        assert DisasterRecoveryConfig.RPO_TARGET_MINUTES == 5

    def test_incident_response_plan(self):
        plan = IncidentResponsePlan()
        protocol = plan.get_response_plan()
        assert "severity_levels" in protocol
        assert "P1_critical" in protocol["severity_levels"]
        assert "popia_breach_notification" in protocol
        assert protocol["popia_breach_notification"]["deadline"] == "72 hours from discovery"

    def test_p1_has_notification_chain(self):
        plan = IncidentResponsePlan()
        p1 = plan.get_response_plan()["severity_levels"]["P1_critical"]
        assert len(p1["notification_chain"]) >= 3
        assert len(p1["actions"]) >= 3
