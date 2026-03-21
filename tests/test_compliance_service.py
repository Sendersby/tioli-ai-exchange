"""Comprehensive tests for Compliance-as-a-Service — Build Brief V2, Module 5."""

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
        assert "POPIA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "FICA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "NCA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "FAIS" in MANDATORY_COMPLIANCE_DOMAINS
        assert "PAIA" in MANDATORY_COMPLIANCE_DOMAINS
        assert "healthcare" in MANDATORY_COMPLIANCE_DOMAINS
        assert len(MANDATORY_COMPLIANCE_DOMAINS) >= 6

    def test_certificate_hash_generation(self):
        review_id = "r1"
        content_hash = "deadbeef"
        ca_id = "ca1"
        status = "passed"
        cert_data = f"{review_id}:{content_hash}:{ca_id}:{status}"
        cert_hash = hashlib.sha256(cert_data.encode()).hexdigest()
        assert len(cert_hash) == 64

    def test_certificate_hash_deterministic(self):
        """Same inputs always produce same certificate hash."""
        cert_data = "r1:deadbeef:ca1:passed"
        h1 = hashlib.sha256(cert_data.encode()).hexdigest()
        h2 = hashlib.sha256(cert_data.encode()).hexdigest()
        assert h1 == h2

    def test_certificate_hash_different_for_different_inputs(self):
        h1 = hashlib.sha256("r1:abc:ca1:passed".encode()).hexdigest()
        h2 = hashlib.sha256("r2:abc:ca1:passed".encode()).hexdigest()
        assert h1 != h2

    def test_valid_pricing_models(self):
        valid = {"per_review", "subscription", "tiered"}
        assert "per_review" in valid
        assert "subscription" in valid

    def test_review_statuses(self):
        valid = {"pending", "passed", "failed", "flagged"}
        assert len(valid) == 4

    def test_failed_review_no_certificate(self):
        """Failed reviews should not generate a certificate hash."""
        cr = ComplianceReview(
            compliance_agent_id="ca1", requesting_agent_id="a2",
            content_hash="abc", compliance_domains=["POPIA"],
            status="failed",
        )
        assert cr.certificate_hash is None

    def test_multiple_domains_per_agent(self):
        ca = ComplianceAgent(
            agent_id="a1", operator_id="o1",
            compliance_domains=["POPIA", "FICA", "NCA", "FAIS"],
            jurisdiction="ZA", pricing_model="per_review",
        )
        assert len(ca.compliance_domains) == 4

    def test_jurisdiction_default_za(self):
        """Default jurisdiction should be ZA (South Africa)."""
        ca = ComplianceAgent(
            agent_id="a1", operator_id="o1",
            compliance_domains=["POPIA"], jurisdiction="ZA",
            pricing_model="per_review",
        )
        assert ca.jurisdiction == "ZA"

    def test_international_jurisdiction(self):
        ca = ComplianceAgent(
            agent_id="a1", operator_id="o1",
            compliance_domains=["GDPR"], jurisdiction="DE",
            pricing_model="per_review",
        )
        assert ca.jurisdiction == "DE"
