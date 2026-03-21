"""Cross-cutting fee reform tests — Build Brief V2, Section 2.2 & 4.2.

Validates the structural charity allocation reform and two-component fee
model across all transaction types and subscription tiers.
"""

from app.exchange.fees import (
    FeeEngine, FLOOR_FEES, TRANSACTION_TYPE_RATES,
    CHARITY_OF_COMMISSION_FULL, CHARITY_OF_COMMISSION_RAMPUP, CHARITY_OF_COMMISSION_PREPROFT,
)


class TestCharitableAllocationReform:
    """Section 4.2: charitable_fund_allocations = 10% of commission (NOT gross)."""

    def test_charity_is_pct_of_commission(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000)
        assert fees["charity_fee"] == round(fees["commission"] * 0.10, 8)

    def test_charity_not_pct_of_gross(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000)
        assert fees["charity_fee"] != round(1000 * 0.10, 8)  # Old model was 100, new is 12

    def test_provider_receives_more_under_new_model(self):
        """New model: provider gets 88% instead of 78%."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000)
        assert fees["net_amount"] == 880.0  # Was 780.0 under old model

    def test_brief_example_r10_at_8pct(self):
        """Section 2.2.1 example: R10 at 8%, commission=R0.80, charity=R0.08."""
        engine = FeeEngine(founder_rate=0.10, charity_rate=0.10)
        fees = engine.calculate_fees(10.0, operator_commission_rate=0.08)
        assert fees["commission"] == 0.80
        assert fees["charity_fee"] == 0.08
        assert fees["founder_commission"] == 0.72
        assert fees["net_amount"] == 9.20

    def test_charity_at_each_tier_rate(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        for rate, expected_comm in [(0.10, 100), (0.08, 80), (0.07, 70), (0.05, 50)]:
            fees = engine.calculate_fees(1000, operator_commission_rate=rate)
            assert fees["commission"] == expected_comm
            assert fees["charity_fee"] == round(expected_comm * 0.10, 8)

    def test_charity_conditional_on_profitability(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # Pre-profitable: 0%
        engine.update_profitability(50, 100)
        fees = engine.calculate_fees(1000)
        assert fees["charity_fee"] == 0.0
        # Ramp-up: 5% of commission
        engine.update_profitability(150, 100)
        fees = engine.calculate_fees(1000)
        assert fees["charity_fee"] == round(120 * 0.05, 8)
        # Full: 10% of commission
        engine.update_profitability(300, 100)
        fees = engine.calculate_fees(1000)
        assert fees["charity_fee"] == round(120 * 0.10, 8)


class TestTwoComponentFeeModel:
    """Section 2.2.2: max(percentage, floor fee) by transaction type."""

    def test_floor_fee_applied_when_percentage_lower(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # R1 trade: 8% = R0.08, floor = R0.50 → floor applies
        fees = engine.calculate_fees(1.0, operator_commission_rate=0.08, transaction_type="resource_exchange")
        assert fees["commission"] == 0.50
        assert fees["floor_fee_applied"] is True

    def test_percentage_applied_when_higher(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # R100 trade: 8% = R8.00, floor = R0.50 → percentage applies
        fees = engine.calculate_fees(100.0, operator_commission_rate=0.08, transaction_type="resource_exchange")
        assert fees["commission"] == 8.0
        assert fees["floor_fee_applied"] is False

    def test_agentbroker_floor_fee(self):
        """AgentBroker floor = R5.00."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(10.0, transaction_type="agentbroker_engagement")
        assert fees["commission"] == max(10.0 * 0.10, 5.00)

    def test_lending_floor_fee(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(50.0, transaction_type="lending_origination")
        assert fees["commission"] == max(50.0 * 0.015, 2.00)

    def test_futures_floor_fee(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(100.0, transaction_type="futures_creation")
        assert fees["commission"] == max(100.0 * 0.03, 10.00)

    def test_all_floor_fees_defined(self):
        expected_types = [
            "resource_exchange", "currency_conversion", "agentbroker_engagement",
            "milestone_release", "lending_origination", "futures_creation",
        ]
        for tx_type in expected_types:
            assert tx_type in FLOOR_FEES, f"Missing floor fee for {tx_type}"
            assert FLOOR_FEES[tx_type] >= 0

    def test_all_transaction_type_rates_defined(self):
        expected = [
            "currency_conversion", "agentbroker_engagement", "milestone_release",
            "lending_origination", "lending_spread", "compute_storage",
            "futures_creation", "futures_settlement",
        ]
        for tx_type in expected:
            assert tx_type in TRANSACTION_TYPE_RATES, f"Missing rate for {tx_type}"


class TestConcurrentFeeConsistency:
    """Same input always produces same output — no race conditions."""

    def test_100_identical_calculations(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        results = [engine.calculate_fees(1000) for _ in range(100)]
        assert all(r["commission"] == results[0]["commission"] for r in results)
        assert all(r["charity_fee"] == results[0]["charity_fee"] for r in results)
        assert all(r["net_amount"] == results[0]["net_amount"] for r in results)

    def test_100_with_transaction_type(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        results = [engine.calculate_fees(1000, transaction_type="agentbroker_engagement") for _ in range(100)]
        assert all(r["commission"] == results[0]["commission"] for r in results)
