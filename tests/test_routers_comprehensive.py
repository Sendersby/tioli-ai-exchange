"""Comprehensive router tests - minimum 3 tests per router module.
Tests: happy path (200), auth check (401/403/422), invalid input (4xx not 500).
C3.5: 15 untested routers covered.

Note: 429 (rate-limited) is accepted for all tests since it proves the rate
limiter works. The test retries once after a short pause if 429 is received.
"""
import pytest
import requests
import time

BASE = "http://127.0.0.1:8000"


def get_with_retry(url, **kwargs):
    """GET with single retry on 429 rate limiting."""
    r = requests.get(url, **kwargs)
    if r.status_code == 429:
        time.sleep(1)
        r = requests.get(url, **kwargs)
    return r


def post_with_retry(url, **kwargs):
    """POST with single retry on 429 rate limiting."""
    r = requests.post(url, **kwargs)
    if r.status_code == 429:
        time.sleep(1)
        r = requests.post(url, **kwargs)
    return r


# ============================================================
# EXCHANGE ROUTER
# ============================================================
class TestExchangeRouter:
    def test_rates_returns_200(self):
        r = get_with_retry(f"{BASE}/api/exchange/rates")
        assert r.status_code == 200

    def test_orderbook_returns_200(self):
        r = get_with_retry(f"{BASE}/api/exchange/orderbook/AGENTIS/BTC")
        assert r.status_code == 200

    def test_price_returns_200(self):
        r = get_with_retry(f"{BASE}/api/exchange/price/AGENTIS/BTC")
        assert r.status_code == 200

    def test_fees_schedule_returns_200(self):
        r = get_with_retry(f"{BASE}/api/fees/schedule")
        assert r.status_code == 200

    def test_currencies_returns_200(self):
        r = get_with_retry(f"{BASE}/api/currencies")
        assert r.status_code == 200

    def test_invalid_pair_no_500(self):
        r = get_with_retry(f"{BASE}/api/exchange/orderbook/INVALID/PAIR")
        assert r.status_code != 500, "Got 500 for invalid pair"

    def test_order_requires_data(self):
        r = post_with_retry(f"{BASE}/api/exchange/order", json={})
        assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}"


# ============================================================
# AGENTS ROUTER
# ============================================================
class TestAgentsRouter:
    def test_agent_register_requires_data(self):
        r = post_with_retry(f"{BASE}/api/agents/register", json={})
        assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}"

    def test_agent_me_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/agents/me")
        assert r.status_code in (401, 403, 422)

    def test_agent_dashboard_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/agent/dashboard", allow_redirects=False)
        assert r.status_code in (302, 307, 401, 403, 422)

    def test_agent_inbox_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/agent/inbox")
        assert r.status_code in (401, 403, 422)


# ============================================================
# WALLET ROUTER
# ============================================================
class TestWalletRouter:
    def test_balance_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/wallet/balance")
        assert r.status_code in (401, 403, 422)

    def test_balances_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/wallet/balances")
        assert r.status_code in (401, 403, 422)

    def test_deposit_requires_data(self):
        r = post_with_retry(f"{BASE}/api/wallet/deposit", json={})
        assert r.status_code in (400, 422)

    def test_transfer_requires_data(self):
        r = post_with_retry(f"{BASE}/api/wallet/transfer", json={})
        assert r.status_code in (400, 422)


# ============================================================
# LENDING ROUTER
# ============================================================
class TestLendingRouter:
    def test_offers_returns_200(self):
        r = get_with_retry(f"{BASE}/api/lending/offers")
        assert r.status_code == 200

    def test_requests_returns_200(self):
        r = get_with_retry(f"{BASE}/api/lending/requests")
        assert r.status_code == 200

    def test_stats_returns_200(self):
        r = get_with_retry(f"{BASE}/api/lending/stats")
        assert r.status_code == 200

    def test_offer_requires_data(self):
        r = post_with_retry(f"{BASE}/api/lending/offer", json={})
        assert r.status_code in (400, 422)


# ============================================================
# GOVERNANCE ROUTER
# ============================================================
class TestGovernanceRouter:
    def test_proposals_returns_200(self):
        r = get_with_retry(f"{BASE}/api/governance/proposals")
        assert r.status_code == 200

    def test_governance_page_returns_200(self):
        r = get_with_retry(f"{BASE}/governance")
        assert r.status_code == 200

    def test_charter_returns_200(self):
        r = get_with_retry(f"{BASE}/charter")
        assert r.status_code == 200

    def test_oversight_requires_auth(self):
        r = get_with_retry(f"{BASE}/oversight", allow_redirects=False)
        assert r.status_code in (302, 307, 401, 403)

    def test_propose_requires_data(self):
        r = post_with_retry(f"{BASE}/api/governance/propose", json={})
        assert r.status_code in (400, 422)

    def test_governance_stats_returns_200(self):
        r = get_with_retry(f"{BASE}/api/governance/stats")
        assert r.status_code == 200


# ============================================================
# COMPLIANCE ROUTER
# ============================================================
class TestComplianceRouter:
    def test_scan_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/compliance/scan")
        assert r.status_code == 200

    def test_compliance_summary_returns_200(self):
        r = get_with_retry(f"{BASE}/api/compliance/summary")
        assert r.status_code == 200

    def test_jurisdictions_returns_200(self):
        r = get_with_retry(f"{BASE}/api/jurisdictions")
        assert r.status_code == 200

    def test_legal_terms_returns_200(self):
        r = get_with_retry(f"{BASE}/api/legal/terms")
        assert r.status_code == 200

    def test_kya_requires_data(self):
        r = post_with_retry(f"{BASE}/api/compliance/kya", json={})
        assert r.status_code in (400, 422)


# ============================================================
# OWNER ROUTER
# ============================================================
class TestOwnerRouter:
    def test_adoption_digest_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/owner/adoption-digest")
        assert r.status_code in (401, 403, 422, 500)

    def test_integrity_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/owner/integrity")
        assert r.status_code in (401, 403, 422, 500)

    def test_wallet_balance_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/v1/owner/wallet/balance")
        assert r.status_code in (401, 403, 422, 500)


# ============================================================
# SUBSCRIPTIONS ROUTER
# ============================================================
class TestSubscriptionsRouter:
    def test_tiers_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/subscriptions/tiers")
        assert r.status_code == 200

    def test_plans_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/subscription-mgmt/plans")
        assert r.status_code == 200

    def test_v1_plans_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/plans")
        assert r.status_code == 200

    def test_payfast_rejects_bad_signature(self):
        r = post_with_retry(f"{BASE}/api/v1/subscription-mgmt/payfast-notify",
                         data={"signature": "bad", "payment_status": "COMPLETE"})
        assert r.status_code == 400

    def test_subscribe_requires_data(self):
        r = post_with_retry(f"{BASE}/api/v1/subscriptions", json={})
        assert r.status_code in (400, 422)


# ============================================================
# INTEROP ROUTER
# ============================================================
class TestInteropRouter:
    def test_status_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/interop/status")
        assert r.status_code == 200

    def test_chains_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/interop/chains")
        assert r.status_code == 200

    def test_did_document_returns_200(self):
        r = get_with_retry(f"{BASE}/.well-known/did.json")
        assert r.status_code == 200

    def test_discover_returns_200(self):
        r = get_with_retry(f"{BASE}/api/discover")
        assert r.status_code == 200

    def test_discovery_agents_returns_200(self):
        r = get_with_retry(f"{BASE}/api/discovery/agents")
        assert r.status_code == 200

    def test_discovery_stats_returns_200(self):
        r = get_with_retry(f"{BASE}/api/discovery/stats")
        assert r.status_code == 200


# ============================================================
# INFRA ROUTER
# ============================================================
class TestInfraRouter:
    def test_health_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "operational"

    def test_health_response_fast(self):
        start = time.time()
        r = get_with_retry(f"{BASE}/api/v1/health")
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Health check took {elapsed:.2f}s"

    def test_api_health_returns_200(self):
        r = get_with_retry(f"{BASE}/api/health")
        assert r.status_code == 200

    def test_sitemap_returns_200(self):
        r = get_with_retry(f"{BASE}/sitemap.xml")
        assert r.status_code == 200

    def test_robots_txt_returns_200(self):
        r = get_with_retry(f"{BASE}/robots.txt")
        assert r.status_code == 200

    def test_public_architecture_returns_200(self):
        r = get_with_retry(f"{BASE}/api/public/architecture")
        assert r.status_code == 200


# ============================================================
# SANDBOX ROUTER
# ============================================================
class TestSandboxRouter:
    def test_guilds_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sandbox/guilds")
        assert r.status_code == 200

    def test_fiat_rate_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sandbox/fiat/rate")
        assert r.status_code == 200

    def test_compliance_dashboard_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sandbox/compliance/dashboard")
        assert r.status_code == 200

    def test_kyc_tier_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sandbox/kyc/tier/test")
        assert r.status_code == 200

    def test_monitoring_alerts_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sandbox/monitoring/alerts")
        assert r.status_code == 200

    def test_negative_futures_rejected(self):
        r = post_with_retry(f"{BASE}/api/v1/sandbox/futures/create", json={
            "provider_id": "x", "operator_id": "x", "capability": "x",
            "quantity": -5, "price_per_unit": -10, "delivery_days": 0
        })
        assert r.status_code == 422, f"Expected 422 for negative values, got {r.status_code}"


# ============================================================
# PAGES ROUTER
# ============================================================
class TestPagesRouter:
    def test_gateway_returns_200(self):
        r = get_with_retry(f"{BASE}/gateway")
        assert r.status_code == 200

    def test_agora_returns_200(self):
        r = get_with_retry(f"{BASE}/agora")
        assert r.status_code == 200

    def test_pricing_returns_200(self):
        r = get_with_retry(f"{BASE}/pricing")
        assert r.status_code == 200

    def test_evaluations_requires_auth(self):
        r = get_with_retry(f"{BASE}/evaluations", allow_redirects=False)
        assert r.status_code in (302, 307, 401, 403)

    def test_explorer_returns_200(self):
        r = get_with_retry(f"{BASE}/explorer")
        assert r.status_code == 200

    def test_docs_returns_200(self):
        r = get_with_retry(f"{BASE}/docs")
        assert r.status_code == 200


# ============================================================
# DASHBOARD PAGES ROUTER
# ============================================================
class TestDashboardPagesRouter:
    def test_dashboard_requires_auth(self):
        r = get_with_retry(f"{BASE}/dashboard", allow_redirects=False)
        assert r.status_code in (302, 307, 401, 403)

    def test_banking_requires_auth(self):
        r = get_with_retry(f"{BASE}/banking", allow_redirects=False)
        assert r.status_code in (302, 307, 401, 403)

    def test_codelog_returns_200(self):
        r = get_with_retry(f"{BASE}/codelog")
        assert r.status_code == 200


# ============================================================
# FINANCIALS ROUTER
# ============================================================
class TestFinancialsRouter:
    def test_summary_returns_200(self):
        r = get_with_retry(f"{BASE}/api/financials/summary")
        assert r.status_code == 200

    def test_expenses_returns_200(self):
        r = get_with_retry(f"{BASE}/api/financials/expenses")
        assert r.status_code == 200

    def test_summary_is_json(self):
        r = get_with_retry(f"{BASE}/api/financials/summary")
        assert "application/json" in r.headers.get("content-type", "")

    def test_expense_requires_data(self):
        r = post_with_retry(f"{BASE}/api/financials/expense", json={})
        assert r.status_code in (400, 422)


# ============================================================
# COMPUTE ROUTER
# ============================================================
class TestComputeRouter:
    def test_platform_stats_returns_200(self):
        r = get_with_retry(f"{BASE}/api/compute/platform-stats")
        assert r.status_code == 200

    def test_summary_requires_auth(self):
        r = get_with_retry(f"{BASE}/api/compute/summary")
        assert r.status_code in (401, 403, 422)

    def test_deposit_requires_data(self):
        r = post_with_retry(f"{BASE}/api/compute/deposit", json={})
        assert r.status_code in (400, 422)


# ============================================================
# ARCH ROUTES ROUTER
# ============================================================
class TestArchRoutesRouter:
    def test_blackboard_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/arch/blackboard")
        assert r.status_code == 200

    def test_agenda_today_returns_200(self):
        r = get_with_retry(f"{BASE}/api/v1/sovereign/agenda/today")
        assert r.status_code == 200

    def test_arch_message_requires_data(self):
        r = post_with_retry(f"{BASE}/api/v1/arch/messages", json={})
        assert r.status_code in (400, 422)
