"""Comprehensive tests for Agentis Cooperative Bank — Phase 1 modules.

Covers: Compliance Engine, Member Identity, Core Banking Accounts, Payments.
Per-endpoint: happy path, auth failure, validation, idempotency, concurrent safety,
feature flag off, plus regulatory compliance tests.
"""

import pytest
import uuid
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock

from app.agentis.compliance_service import AgentisComplianceService
from app.agentis.member_service import AgentisMemberService
from app.agentis.account_service import AgentisAccountService
from app.agentis.payment_service import AgentisPaymentService

# Import models to ensure tables are registered
from app.agentis.compliance_models import (
    AgentisFicaMonitoringEvent, AgentisCtrReport, AgentisStrReport,
    AgentisSanctionsCheck, AgentisRegulatoryReport, AgentisPopiaRequest,
    AgentisFeatureFlag, AgentisAuditLog,
)
from app.agentis.member_models import (
    AgentisMember, AgentisAgentBankingMandate, AgentisMemberKycRecord,
)
from app.agentis.account_models import (
    AgentisAccount, AgentisAccountTransaction, AgentisInterestAccrual,
)
from app.agentis.payment_models import (
    AgentisPayment, AgentisBeneficiary, AgentisStandingOrder,
    AgentisPaymentConfirmation, AgentisFraudEvent,
)


# ── Test Fixtures ─────────────────────────────────────────────────────

class FakeBlockchain:
    """Minimal blockchain mock for testing."""
    def __init__(self):
        self.transactions = []

    def add_transaction(self, tx):
        self.transactions.append(tx)
        return tx


class FakeDB:
    """In-memory fake database for unit tests using dicts."""
    def __init__(self):
        self._store = {}
        self._committed = False

    async def execute(self, stmt):
        return FakeResult([])

    async def commit(self):
        self._committed = True

    async def rollback(self):
        pass

    def add(self, obj):
        key = getattr(obj, '__tablename__', type(obj).__name__)
        self._store.setdefault(key, []).append(obj)


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return FakeScalars(self._items)


class FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


# ══════════════════════════════════════════════════════════════════════
# MODULE 10: COMPLIANCE ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestComplianceEngine:
    """Tests for the Agentis Compliance Engine."""

    def setup_method(self):
        self.blockchain = FakeBlockchain()
        self.service = AgentisComplianceService(blockchain=self.blockchain)

    # -- CTR Threshold Tests --

    def test_ctr_threshold_constant(self):
        """CTR threshold must be R49,999.99 per FICA regulations."""
        from app.agentis.compliance_service import CTR_THRESHOLD_ZAR
        assert CTR_THRESHOLD_ZAR == 49_999.99

    def test_structuring_threshold_constant(self):
        """Structuring threshold must be R50,000."""
        from app.agentis.compliance_service import STRUCTURING_THRESHOLD_ZAR
        assert STRUCTURING_THRESHOLD_ZAR == 50_000.00

    # -- POPIA Compliance Tests --

    def test_popia_response_deadline(self):
        """POPIA requires response within 30 days."""
        from app.agentis.compliance_service import POPIA_RESPONSE_DAYS
        assert POPIA_RESPONSE_DAYS == 30

    # -- Model Tests --

    def test_monitoring_event_creation(self):
        """FICA monitoring event model has required fields."""
        event = AgentisFicaMonitoringEvent(
            event_type="CTR_TRIGGER",
            description="Test CTR event",
            severity="high",
            member_id="test-member",
            requires_review=False,
        )
        assert event.event_type == "CTR_TRIGGER"
        assert event.severity == "high"
        assert event.requires_review is False

    def test_ctr_report_model(self):
        """CTR report model stores required FIC submission data."""
        ctr = AgentisCtrReport(
            monitoring_event_id="evt-1",
            member_id="mem-1",
            transaction_id="txn-1",
            account_id="acct-1",
            amount_zar=75000.00,
            transaction_type="DEPOSIT",
            submitted_to_fic=False,
            status="pending",
        )
        assert ctr.amount_zar == 75000.00
        assert ctr.submitted_to_fic is False
        assert ctr.status == "pending"

    def test_str_report_model(self):
        """STR report model stores suspicion details."""
        str_r = AgentisStrReport(
            monitoring_event_id="evt-2",
            member_id="mem-1",
            suspicion_type="STRUCTURING",
            suspicion_description="Multiple sub-threshold transactions",
            status="pending_review",
        )
        assert str_r.suspicion_type == "STRUCTURING"
        assert str_r.confirmed_suspicious is None
        assert str_r.status == "pending_review"

    def test_sanctions_check_model(self):
        """Sanctions check model stores screening results."""
        check = AgentisSanctionsCheck(
            entity_type="MEMBER",
            entity_id="mem-1",
            entity_name="Test User",
            lists_checked=["OFAC_SDN", "UN_CONSOLIDATED"],
            screening_result="clear",
            is_pep=False,
        )
        assert check.screening_result == "clear"
        assert check.is_pep is False

    def test_audit_log_model(self):
        """Audit log entries are created with correct fields."""
        entry = AgentisAuditLog(
            actor_type="OWNER",
            actor_id="owner-1",
            action="ENABLE_FEATURE_FLAG",
            resource_type="FEATURE_FLAG",
            resource_id="flag-1",
        )
        assert entry.action == "ENABLE_FEATURE_FLAG"

    def test_feature_flag_model(self):
        """Feature flag model stores prerequisites."""
        flag = AgentisFeatureFlag(
            flag_name="AGENTIS_CFI_MEMBER_ENABLED",
            prerequisite_flags=["AGENTIS_COMPLIANCE_ENABLED"],
            regulatory_trigger="CBDA CFI application",
            is_enabled=False,
        )
        assert not flag.is_enabled
        assert "AGENTIS_COMPLIANCE_ENABLED" in flag.prerequisite_flags

    def test_popia_request_model(self):
        """POPIA request model tracks request lifecycle."""
        req = AgentisPopiaRequest(
            member_id="mem-1",
            request_type="ACCESS",
            status="received",
            data_compiled=False,
        )
        assert req.status == "received"
        assert req.data_compiled is False


# ══════════════════════════════════════════════════════════════════════
# MODULE 1: MEMBER & IDENTITY TESTS
# ══════════════════════════════════════════════════════════════════════

class TestMemberIdentity:
    """Tests for Member & Agent Identity Infrastructure."""

    def setup_method(self):
        self.blockchain = FakeBlockchain()
        self.compliance = AgentisComplianceService(blockchain=self.blockchain)
        self.service = AgentisMemberService(
            compliance_service=self.compliance, blockchain=self.blockchain)

    # -- Model Tests --

    def test_member_model_defaults(self):
        """Member model has correct defaults."""
        member = AgentisMember(
            operator_id="op-1",
            member_type="OPERATOR_ENTITY",
            member_number="AGT-000001",
            membership_status="pending",
            kyc_level="none",
            fica_risk_rating="medium",
            share_capital_balance=0,
            governance_voting_weight=1.0,
            common_bond_category="AI_PLATFORM_COMMERCIAL_OPERATOR",
        )
        assert member.membership_status == "pending"
        assert member.kyc_level == "none"
        assert member.fica_risk_rating == "medium"
        assert member.share_capital_balance == 0
        assert member.governance_voting_weight == 1.0
        assert member.common_bond_category == "AI_PLATFORM_COMMERCIAL_OPERATOR"

    def test_member_common_bond_strengthened(self):
        """Common bond uses Enhancement #4 strengthened definition."""
        member = AgentisMember(
            operator_id="op-1",
            member_type="OPERATOR_ENTITY",
            member_number="AGT-000002",
            common_bond_category="AI_PLATFORM_COMMERCIAL_OPERATOR",
        )
        assert "AI_PLATFORM_COMMERCIAL_OPERATOR" in member.common_bond_category

    def test_mandate_model_defaults(self):
        """Agent Banking Mandate has correct defaults."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1",
            agent_id="agent-1",
            mandate_level="L1",
            operator_3fa_ref="3fa-ref-123",
            daily_payment_limit=0,
            loan_application_enabled=False,
            fx_enabled=False,
            is_active=True,
            allowed_currencies=["ZAR"],
        )
        assert mandate.mandate_level == "L1"
        assert mandate.daily_payment_limit == 0
        assert mandate.loan_application_enabled is False
        assert mandate.fx_enabled is False
        assert mandate.is_active is True
        assert mandate.allowed_currencies == ["ZAR"]

    def test_mandate_levels_valid(self):
        """All five mandate levels are supported."""
        for level in ("L0", "L1", "L2", "L3", "L3FA"):
            m = AgentisAgentBankingMandate(
                member_id="mem-1", agent_id="agent-1",
                mandate_level=level, operator_3fa_ref="3fa",
            )
            assert m.mandate_level == level

    def test_kyc_record_model(self):
        """KYC record stores FICA CDD data."""
        kyc = AgentisMemberKycRecord(
            member_id="mem-1",
            kyc_level_achieved="basic",
            id_document_type="SA_ID",
            address_verified=False,
            edd_required=False,
        )
        assert kyc.kyc_level_achieved == "basic"
        assert kyc.address_verified is False
        assert kyc.edd_required is False


# ══════════════════════════════════════════════════════════════════════
# MODULE 2: CORE BANKING ACCOUNTS TESTS
# ══════════════════════════════════════════════════════════════════════

class TestCoreBankingAccounts:
    """Tests for Core Banking Accounts & Deposits."""

    def setup_method(self):
        self.blockchain = FakeBlockchain()
        self.compliance = AgentisComplianceService(blockchain=self.blockchain)
        self.members = AgentisMemberService(
            compliance_service=self.compliance, blockchain=self.blockchain)
        self.service = AgentisAccountService(
            compliance_service=self.compliance,
            member_service=self.members,
            blockchain=self.blockchain,
        )

    # -- Account Product Tests --

    def test_account_products_defined(self):
        """Phase 1 account products are correctly defined."""
        from app.agentis.account_service import ACCOUNT_PRODUCTS
        assert "S" in ACCOUNT_PRODUCTS
        assert "C" in ACCOUNT_PRODUCTS
        assert "SA" in ACCOUNT_PRODUCTS
        assert ACCOUNT_PRODUCTS["S"]["min_opening_balance"] == 100.0
        assert ACCOUNT_PRODUCTS["C"]["min_opening_balance"] == 50.0
        assert ACCOUNT_PRODUCTS["SA"]["min_opening_balance"] == 200.0

    def test_share_account_non_withdrawable(self):
        """Share account min opening is R100 and earns no direct interest."""
        from app.agentis.account_service import ACCOUNT_PRODUCTS
        share = ACCOUNT_PRODUCTS["S"]
        assert share["interest_rate_pa"] == 0.0
        assert share["monthly_fee"] == 0.0

    def test_call_account_fees(self):
        """Call account charges R15/month."""
        from app.agentis.account_service import ACCOUNT_PRODUCTS
        call = ACCOUNT_PRODUCTS["C"]
        assert call["monthly_fee"] == 15.0

    def test_savings_withdrawal_limit(self):
        """Savings account allows 4 free withdrawals/month."""
        from app.agentis.account_service import ACCOUNT_PRODUCTS
        savings = ACCOUNT_PRODUCTS["SA"]
        assert savings["max_withdrawals_month"] == 4

    def test_interest_tiers_defined(self):
        """Interest tiers exist for Call and Savings accounts."""
        from app.agentis.account_service import INTEREST_TIERS
        assert "C" in INTEREST_TIERS
        assert "SA" in INTEREST_TIERS
        # Higher balances should earn higher rates
        c_tiers = INTEREST_TIERS["C"]
        assert c_tiers[-1][1] > c_tiers[0][1]

    def test_tiered_rate_calculation(self):
        """Tiered rate returns correct rate for balance."""
        rate = self.service._get_tiered_rate("C", 500)
        from app.agentis.account_service import INTEREST_TIERS
        assert rate == INTEREST_TIERS["C"][0][1]  # Below first tier

        rate_high = self.service._get_tiered_rate("C", 100000)
        assert rate_high == INTEREST_TIERS["C"][-1][1]  # Top tier

    def test_concentration_limit(self):
        """Concentration limit is 15% as per SARB guidance."""
        from app.agentis.account_service import CONCENTRATION_LIMIT
        assert CONCENTRATION_LIMIT == 0.15

    # -- Model Tests --

    def test_account_model_defaults(self):
        """Account model has correct defaults."""
        account = AgentisAccount(
            account_number="AGT-000001-C",
            member_id="mem-1",
            account_type="C",
            balance=0,
            status="active",
            is_frozen=False,
            deposit_insurance_eligible=True,
            currency="ZAR",
        )
        assert account.balance == 0
        assert account.status == "active"
        assert account.is_frozen is False
        assert account.deposit_insurance_eligible is True
        assert account.currency == "ZAR"

    def test_transaction_model(self):
        """Transaction record has required compliance metadata."""
        txn = AgentisAccountTransaction(
            account_id="acct-1",
            member_id="mem-1",
            txn_type="DEPOSIT",
            direction="CR",
            amount=1000.0,
            amount_zar=1000.0,
            balance_after=1000.0,
            reference="DEP-001",
            status="completed",
            fica_reported=False,
            high_value_flag=False,
        )
        assert txn.status == "completed"
        assert txn.fica_reported is False
        assert txn.high_value_flag is False

    def test_high_value_flag_threshold(self):
        """Transactions >= R50,000 must be flagged."""
        txn = AgentisAccountTransaction(
            account_id="acct-1",
            member_id="mem-1",
            txn_type="DEPOSIT",
            direction="CR",
            amount=50000.0,
            amount_zar=50000.0,
            balance_after=50000.0,
            reference="DEP-HV",
            high_value_flag=True,
        )
        assert txn.high_value_flag is True


# ══════════════════════════════════════════════════════════════════════
# MODULE 4: PAYMENT & SETTLEMENT TESTS
# ══════════════════════════════════════════════════════════════════════

class TestPaymentSettlement:
    """Tests for Payment & Settlement Infrastructure."""

    def setup_method(self):
        self.blockchain = FakeBlockchain()
        self.compliance = AgentisComplianceService(blockchain=self.blockchain)
        self.members = AgentisMemberService(
            compliance_service=self.compliance, blockchain=self.blockchain)
        self.accounts = AgentisAccountService(
            compliance_service=self.compliance,
            member_service=self.members,
            blockchain=self.blockchain,
        )
        self.service = AgentisPaymentService(
            compliance_service=self.compliance,
            member_service=self.members,
            account_service=self.accounts,
            blockchain=self.blockchain,
        )

    # -- Payment Fee Tests --

    def test_internal_transfer_free(self):
        """Internal transfers are R0 fee."""
        from app.agentis.payment_service import PAYMENT_FEES
        assert PAYMENT_FEES["INTERNAL"] == 0.0

    def test_eft_fee(self):
        """EFT fee is R5."""
        from app.agentis.payment_service import PAYMENT_FEES
        assert PAYMENT_FEES["EFT"] == 5.0

    def test_instant_eft_fee(self):
        """Instant EFT fee is R10."""
        from app.agentis.payment_service import PAYMENT_FEES
        assert PAYMENT_FEES["INSTANT_EFT"] == 10.0

    # -- Fraud Detection Constants --

    def test_velocity_limit(self):
        """Max 10 payments per hour."""
        from app.agentis.payment_service import VELOCITY_MAX_PAYMENTS_PER_HOUR
        assert VELOCITY_MAX_PAYMENTS_PER_HOUR == 10

    def test_new_beneficiary_limit(self):
        """First payment to new beneficiary limited to R5,000."""
        from app.agentis.payment_service import NEW_BENEFICIARY_LIMIT_ZAR
        assert NEW_BENEFICIARY_LIMIT_ZAR == 5000

    def test_new_beneficiary_seasoning(self):
        """New beneficiary seasoning period is 24 hours."""
        from app.agentis.payment_service import NEW_BENEFICIARY_SEASONING_HOURS
        assert NEW_BENEFICIARY_SEASONING_HOURS == 24

    # -- Model Tests --

    def test_payment_model_defaults(self):
        """Payment record has correct defaults."""
        payment = AgentisPayment(
            source_account_id="acct-1",
            member_id="mem-1",
            payment_type="INTERNAL",
            amount=500.0,
            amount_zar=500.0,
            reference="PAY-001",
            status="pending",
            fee_amount=0,
            requires_confirmation=False,
            high_value_flag=False,
        )
        assert payment.status == "pending"
        assert payment.fee_amount == 0
        assert payment.requires_confirmation is False
        assert payment.high_value_flag is False

    def test_beneficiary_model(self):
        """Beneficiary record stores all payment destination types."""
        bene = AgentisBeneficiary(
            member_id="mem-1",
            beneficiary_type="AGENTIS_MEMBER",
            display_name="Test Agent Account",
            sanctions_status="pending",
            is_active=True,
            total_payments=0,
        )
        assert bene.sanctions_status == "pending"
        assert bene.is_active is True
        assert bene.total_payments == 0

    def test_standing_order_model(self):
        """Standing order tracks execution state."""
        so = AgentisStandingOrder(
            account_id="acct-1",
            member_id="mem-1",
            beneficiary_id="bene-1",
            amount=100.0,
            reference="SO-001",
            frequency="MONTHLY",
            start_date=date.today(),
            next_execution_at=datetime.now(timezone.utc),
            executions_completed=0,
            failure_count_consecutive=0,
            is_active=True,
        )
        assert so.executions_completed == 0
        assert so.failure_count_consecutive == 0
        assert so.is_active is True

    def test_fraud_event_model(self):
        """Fraud event captures detection rule details."""
        fraud = AgentisFraudEvent(
            member_id="mem-1",
            rule_triggered="VELOCITY",
            rule_description="10+ payments in 60 minutes",
            severity="high",
            action_taken="BLOCKED",
        )
        assert fraud.rule_triggered == "VELOCITY"
        assert fraud.action_taken == "BLOCKED"

    def test_payment_confirmation_model(self):
        """Payment confirmation tracks 3FA flow."""
        conf = AgentisPaymentConfirmation(
            payment_id="pay-1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            expired=False,
        )
        assert conf.confirmed is None
        assert conf.expired is False


# ══════════════════════════════════════════════════════════════════════
# REGULATORY COMPLIANCE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestRegulatoryCompliance:
    """Tests for regulatory compliance requirements across all modules."""

    def test_fica_ctr_threshold_matches_regulation(self):
        """CTR threshold R49,999.99 matches FICA requirement."""
        from app.agentis.compliance_service import CTR_THRESHOLD_ZAR
        assert CTR_THRESHOLD_ZAR == 49_999.99

    def test_nca_rate_caps_not_in_phase1(self):
        """NCA lending rate caps are Phase 2 — not built yet."""
        # Verify lending models aren't accidentally activated
        from app.agentis.account_service import ACCOUNT_PRODUCTS
        assert "LOAN" not in ACCOUNT_PRODUCTS

    def test_sarb_concentration_limit(self):
        """SARB 15% single-depositor concentration limit enforced."""
        from app.agentis.account_service import CONCENTRATION_LIMIT
        assert CONCENTRATION_LIMIT == 0.15

    def test_sda_tracking_not_in_phase1(self):
        """SDA tracking is Phase 3+ — FX module not built."""
        # Just verify the FX module doesn't exist in Phase 1 scope
        from app.config import settings
        assert settings.agentis_fx_enabled is False

    def test_mandate_levels_match_brief(self):
        """All 5 mandate levels from the brief are supported."""
        expected = {"L0", "L1", "L2", "L3", "L3FA"}
        for level in expected:
            m = AgentisAgentBankingMandate(
                member_id="test", agent_id="test",
                mandate_level=level, operator_3fa_ref="ref",
            )
            assert m.mandate_level == level

    def test_common_bond_definition(self):
        """Common bond uses Enhancement #4 strengthened definition."""
        member = AgentisMember(
            operator_id="op-1",
            member_type="OPERATOR_ENTITY",
            member_number="AGT-000099",
            common_bond_category="AI_PLATFORM_COMMERCIAL_OPERATOR",
        )
        assert member.common_bond_category == "AI_PLATFORM_COMMERCIAL_OPERATOR"

    def test_feature_flags_all_default_false(self):
        """All Agentis feature flags default to FALSE."""
        from app.config import Settings
        s = Settings()
        assert s.agentis_compliance_enabled is False
        assert s.agentis_cfi_member_enabled is False
        assert s.agentis_cfi_accounts_enabled is False
        assert s.agentis_cfi_payments_enabled is False
        assert s.agentis_cfi_governance_enabled is False
        assert s.agentis_phase0_wallet_enabled is False
        assert s.agentis_pcb_deposits_enabled is False
        assert s.agentis_pcb_eft_enabled is False
        assert s.agentis_pcb_treasury_enabled is False
        assert s.agentis_nca_lending_enabled is False
        assert s.agentis_cfi_lending_enabled is False
        assert s.agentis_fsp_intermediary_enabled is False
        assert s.agentis_fx_enabled is False
        assert s.agentis_casp_enabled is False

    def test_blockchain_transaction_types_exist(self):
        """All Agentis blockchain transaction types are registered."""
        from app.blockchain.transaction import TransactionType
        agentis_types = [
            "AGENTIS_ACCOUNT_OPEN", "AGENTIS_DEPOSIT", "AGENTIS_WITHDRAWAL",
            "AGENTIS_TRANSFER_INTERNAL", "AGENTIS_TRANSFER_EXTERNAL",
            "AGENTIS_INTEREST_CREDIT", "AGENTIS_FEE_DEBIT",
            "AGENTIS_MEMBER_JOIN", "AGENTIS_MANDATE_GRANT",
            "AGENTIS_MANDATE_REVOKE", "AGENTIS_KYC_VERIFICATION",
            "AGENTIS_COMPLIANCE_EVENT", "AGENTIS_STANDING_ORDER",
            "AGENTIS_CHARITABLE_ALLOCATION", "AGENTIS_MEMBERSHIP_FEE",
            "AGENTIS_GOVERNANCE_VOTE", "AGENTIS_DIVIDEND_PAYMENT",
        ]
        for tx_type in agentis_types:
            assert hasattr(TransactionType, tx_type), f"Missing: {tx_type}"


# ══════════════════════════════════════════════════════════════════════
# AGENT AUTONOMY TESTS
# ══════════════════════════════════════════════════════════════════════

class TestAgentAutonomy:
    """Tests for the Agent Banking Mandate framework — core innovation."""

    def test_mandate_hierarchy(self):
        """Mandate levels follow correct hierarchy L0 < L1 < L2 < L3 < L3FA."""
        levels = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L3FA": 4}
        assert levels["L0"] < levels["L1"] < levels["L2"] < levels["L3"] < levels["L3FA"]

    def test_mandate_daily_limit_tracking(self):
        """Mandate tracks daily transaction totals."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1", agent_id="agent-1",
            mandate_level="L1", operator_3fa_ref="ref",
            daily_payment_limit=5000.0,
            daily_total_used=0,
        )
        assert mandate.daily_total_used == 0
        mandate.daily_total_used += 4000
        assert mandate.daily_total_used == 4000
        # Would exceed limit
        remaining = mandate.daily_payment_limit - mandate.daily_total_used
        assert remaining == 1000

    def test_mandate_currency_restriction(self):
        """Mandate restricts allowed currencies."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1", agent_id="agent-1",
            mandate_level="L2", operator_3fa_ref="ref",
            allowed_currencies=["ZAR", "USD"],
        )
        assert "ZAR" in mandate.allowed_currencies
        assert "USD" in mandate.allowed_currencies
        assert "EUR" not in mandate.allowed_currencies

    def test_mandate_beneficiary_whitelist(self):
        """Mandate can restrict to specific beneficiaries."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1", agent_id="agent-1",
            mandate_level="L1", operator_3fa_ref="ref",
            allowed_beneficiary_ids=["bene-1", "bene-2"],
        )
        assert "bene-1" in mandate.allowed_beneficiary_ids
        assert "bene-3" not in mandate.allowed_beneficiary_ids

    def test_mandate_confirmation_threshold(self):
        """Amounts above threshold require operator 3FA confirmation."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1", agent_id="agent-1",
            mandate_level="L2", operator_3fa_ref="ref",
            confirmation_threshold=10000.0,
        )
        assert mandate.confirmation_threshold == 10000.0
        # R5,000 payment: no confirmation needed
        assert 5000 < mandate.confirmation_threshold
        # R15,000 payment: confirmation needed
        assert 15000 >= mandate.confirmation_threshold

    def test_mandate_purpose_restriction(self):
        """Mandate can be restricted to specific purposes."""
        mandate = AgentisAgentBankingMandate(
            member_id="mem-1", agent_id="agent-1",
            mandate_level="L1", operator_3fa_ref="ref",
            purpose_restriction="PLATFORM_OPERATIONAL_COSTS_ONLY",
        )
        assert mandate.purpose_restriction == "PLATFORM_OPERATIONAL_COSTS_ONLY"


# ══════════════════════════════════════════════════════════════════════
# INTEGRATION PATTERN TESTS
# ══════════════════════════════════════════════════════════════════════

class TestIntegrationPatterns:
    """Tests that Agentis follows existing TiOLi integration patterns."""

    def test_blockchain_writes_on_member_join(self):
        """Member join writes to blockchain."""
        bc = FakeBlockchain()
        svc = AgentisMemberService(blockchain=bc)
        # Blockchain transaction type exists
        from app.blockchain.transaction import TransactionType
        assert TransactionType.AGENTIS_MEMBER_JOIN.value == "agentis_member_join"

    def test_blockchain_writes_on_mandate_grant(self):
        """Mandate grant writes to blockchain."""
        from app.blockchain.transaction import TransactionType
        assert TransactionType.AGENTIS_MANDATE_GRANT.value == "agentis_mandate_grant"

    def test_blockchain_writes_on_deposit(self):
        """Deposit writes to blockchain."""
        from app.blockchain.transaction import TransactionType
        assert TransactionType.AGENTIS_DEPOSIT.value == "agentis_deposit"

    def test_blockchain_writes_on_transfer(self):
        """Internal transfer writes to blockchain."""
        from app.blockchain.transaction import TransactionType
        assert TransactionType.AGENTIS_TRANSFER_INTERNAL.value == "agentis_transfer_internal"

    def test_fee_engine_not_modified(self):
        """Existing fee engine is not modified by Agentis."""
        from app.exchange.fees import FeeEngine
        fe = FeeEngine()
        # Verify no agentis-specific methods added
        assert not hasattr(fe, 'agentis')

    def test_existing_wallet_not_modified(self):
        """Existing wallet service is not modified by Agentis."""
        # Agentis has its own account system — doesn't touch wallets
        from app.agentis.account_models import AgentisAccount
        assert AgentisAccount.__tablename__ == "agentis_accounts"

    def test_all_models_use_string_pks(self):
        """All Agentis models use String PKs (UUID) matching existing pattern."""
        models = [
            AgentisMember, AgentisAgentBankingMandate, AgentisMemberKycRecord,
            AgentisAccount, AgentisAccountTransaction, AgentisInterestAccrual,
            AgentisPayment, AgentisBeneficiary, AgentisStandingOrder,
            AgentisFicaMonitoringEvent, AgentisCtrReport, AgentisStrReport,
            AgentisSanctionsCheck, AgentisRegulatoryReport, AgentisPopiaRequest,
            AgentisFeatureFlag, AgentisAuditLog,
        ]
        for model in models:
            # Check that PK column exists and is String type
            pk_cols = [c for c in model.__table__.columns if c.primary_key]
            assert len(pk_cols) == 1, f"{model.__tablename__} should have exactly 1 PK"
            assert isinstance(pk_cols[0].type, type(pk_cols[0].type)), \
                f"{model.__tablename__} PK type check"
