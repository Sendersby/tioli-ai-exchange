"""Integration tests for critical end-to-end workflows.
C3.6: Sandbox lifecycle, security, and performance integration tests.
"""
import pytest
import requests
import time
import uuid

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


def delete_with_retry(url, **kwargs):
    """DELETE with single retry on 429 rate limiting."""
    r = requests.delete(url, **kwargs)
    if r.status_code == 429:
        time.sleep(1)
        r = requests.delete(url, **kwargs)
    return r


class TestSandboxWorkflow:
    """Test: vault store -> retrieve -> delete flow."""

    def test_vault_lifecycle(self):
        # Store
        r = post_with_retry(f"{BASE}/api/v1/sandbox/vault/store", json={
            "vault_id": "integration-test", "key": "test-key",
            "value": "test-value", "tier": "AV-CACHE"
        })
        assert r.status_code == 200

        # Retrieve
        r = get_with_retry(f"{BASE}/api/v1/sandbox/vault/retrieve/integration-test/test-key")
        assert r.status_code == 200
        data = r.json()
        assert data.get("value") == "test-value" or "test-value" in r.text

        # Delete
        r = delete_with_retry(f"{BASE}/api/v1/sandbox/vault/remove/integration-test/test-key")
        assert r.status_code == 200

    def test_guild_lifecycle(self):
        # Create (unique name to avoid duplicate key errors)
        unique_name = f"IntTest Guild {uuid.uuid4().hex[:8]}"
        r = post_with_retry(f"{BASE}/api/v1/sandbox/guild/create", json={
            "name": unique_name, "operator_id": "int-op",
            "description": "test"
        })
        assert r.status_code == 200
        guild_id = r.json().get("guild_id")
        assert guild_id

        # Join
        r = post_with_retry(f"{BASE}/api/v1/sandbox/guild/{guild_id}/join", json={
            "operator_id": "int-op-2", "role": "member"
        })
        assert r.status_code == 200

        # Detail
        r = get_with_retry(f"{BASE}/api/v1/sandbox/guild/{guild_id}")
        assert r.status_code == 200

    def test_futures_lifecycle(self):
        # Create
        r = post_with_retry(f"{BASE}/api/v1/sandbox/futures/create", json={
            "provider_id": "int-prov", "operator_id": "int-op",
            "capability": "Integration Testing", "quantity": 5,
            "price_per_unit": 20, "delivery_days": 14
        })
        assert r.status_code == 200
        future_id = r.json().get("future_id")
        assert future_id

        # Reserve
        r = post_with_retry(f"{BASE}/api/v1/sandbox/futures/{future_id}/reserve", json={
            "buyer_id": "int-buyer", "quantity": 2
        })
        assert r.status_code == 200

        # Settle
        r = post_with_retry(f"{BASE}/api/v1/sandbox/futures/{future_id}/settle")
        assert r.status_code == 200


class TestSecurityWorkflow:
    """Test: XSS blocked, PayFast verified, auth enforced."""

    def test_xss_blocked(self):
        xss_name = f"<script>alert(1)</script> {uuid.uuid4().hex[:8]}"
        r = post_with_retry(f"{BASE}/api/v1/sandbox/guild/create", json={
            "name": xss_name, "operator_id": "sec-test",
            "description": "test"
        })
        assert "<script>" not in r.text

    def test_payfast_signature_required(self):
        r = post_with_retry(f"{BASE}/api/v1/subscription-mgmt/payfast-notify",
                         data={"payment_status": "COMPLETE", "signature": "fake"})
        assert r.status_code == 400

    def test_negative_amount_rejected(self):
        r = post_with_retry(f"{BASE}/api/v1/sandbox/futures/create", json={
            "provider_id": "x", "operator_id": "x", "capability": "x",
            "quantity": -1, "price_per_unit": -10, "delivery_days": 0
        })
        assert r.status_code == 422


class TestPerformance:
    """Test: critical endpoints respond within acceptable time."""

    def test_health_under_1s(self):
        start = time.time()
        r = get_with_retry(f"{BASE}/api/v1/health")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 1.0, f"Health took {elapsed:.2f}s"

    def test_rates_under_1s(self):
        start = time.time()
        r = get_with_retry(f"{BASE}/api/exchange/rates")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 1.0, f"Rates took {elapsed:.2f}s"

    def test_proposals_under_1s(self):
        start = time.time()
        r = get_with_retry(f"{BASE}/api/governance/proposals")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 1.0, f"Proposals took {elapsed:.2f}s"
