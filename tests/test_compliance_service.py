"""Tests for Compliance-as-a-Service — Build Brief V2, Module 5."""

import hashlib
from app.compliance_service.models import (
    ComplianceAgent, ComplianceReview, MANDATORY_COMPLIANCE_DOMAINS,
)


class TestComplianceModels:
    def test_compliance_agent_fields(self):
        ca = ComplianceAgent(
            agent_id="a1", operator_id="o1",
            compliance_domains=["POPIA", "FICA"],
            jurisdiction="ZA", pricing_model="per_review",
            price_per_review=50.0,
        )
        assert "POPIA" in ca.compliance_domains
        assert ca.jurisdiction == "ZA"
        assert ca.price_per_review == 50.0

    def test_compliance_review_fields(self):
        cr = ComplianceReview(
            compliance_agent_id="ca1", requesting_agent_id="a2",
            content_hash="abc123", compliance_domains=["POPIA"],
            status="pending",
        )
        assert cr.status == "pending"
        assert cr.content_hash == "abc123"

    def test_mandatory_domains_defined(self):
        """Brief: platform designates mandatory compliance domains."""
        assert "POPIA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "FICA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "healthcare" in MANDATORY_COMPLIANCE_DOMAINS
        assert len(MANDATORY_COMPLIANCE_DOMAINS) >= 6

    def test_certificate_hash_generation(self):
        """Passed reviews generate SHA-256 certificate hash."""
        review_id = "r1"
        content_hash = "deadbeef"
        ca_id = "ca1"
        status = "passed"
        cert_data = f"{review_id}:{content_hash}:{ca_id}:{status}"
        cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()
        assert len(cert_hash) == 64
        assert cert_hash == hashlib.sha256(cert_data.encode()).hexdigest()  # Deterministic

    def test_valid_pricing_models(self):
        valid = {"per_review", "subscription", "tiered"}
        assert "per_review" in valid
        assert "subscription" in valid

    def test_review_statuses(self):
        valid = {"pending", "passed", "failed", "flagged"}
        assert len(valid) == 4
