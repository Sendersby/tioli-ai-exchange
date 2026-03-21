"""Compliance-as-a-Service — compliance agent registration, review, and certification.

Build Brief V2, Module 5: Standard AgentBroker commission on each compliance
review. Platform may mandate compliance review for flagged transaction types.
"""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance_service.models import (
    ComplianceAgent, ComplianceReview, MANDATORY_COMPLIANCE_DOMAINS,
)
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class ComplianceService:
    """Manages compliance agent registration, reviews, and certifications."""

    async def register_compliance_agent(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        compliance_domains: list[str], jurisdiction: str = "ZA",
        certification_body: str | None = None, certification_ref: str | None = None,
        review_turnaround_minutes: int = 60,
        pricing_model: str = "per_review", price_per_review: float = 50.0,
    ) -> dict:
        """Register an agent as a compliance specialist."""
        # Verify agent exists
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        if not agent_result.scalar_one_or_none():
            raise ValueError(f"Agent '{agent_id}' not found")

        # Check not already registered
        existing = await db.execute(
            select(ComplianceAgent).where(ComplianceAgent.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent is already registered as a compliance agent")

        if not compliance_domains:
            raise ValueError("At least one compliance domain required")

        valid_models = {"per_review", "subscription", "tiered"}
        if pricing_model not in valid_models:
            raise ValueError(f"Invalid pricing model. Allowed: {valid_models}")

        compliance_agent = ComplianceAgent(
            agent_id=agent_id,
            operator_id=operator_id,
            compliance_domains=compliance_domains,
            jurisdiction=jurisdiction,
            certification_body=certification_body,
            certification_ref=certification_ref,
            review_turnaround_minutes=review_turnaround_minutes,
            pricing_model=pricing_model,
            price_per_review=price_per_review,
        )
        db.add(compliance_agent)
        await db.flush()

        return {
            "compliance_agent_id": compliance_agent.id,
            "agent_id": agent_id,
            "domains": compliance_domains,
            "jurisdiction": jurisdiction,
            "pricing_model": pricing_model,
            "price_per_review": price_per_review,
        }

    async def search_compliance_agents(
        self, db: AsyncSession,
        domain: str | None = None, jurisdiction: str | None = None,
        max_price: float | None = None, limit: int = 50,
    ) -> list[dict]:
        """Search compliance agents by domain, jurisdiction, price."""
        query = select(ComplianceAgent).where(ComplianceAgent.is_active == True)

        if jurisdiction:
            query = query.where(ComplianceAgent.jurisdiction == jurisdiction.upper())
        if max_price is not None:
            query = query.where(ComplianceAgent.price_per_review <= max_price)

        query = query.order_by(ComplianceAgent.reputation_score.desc()).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        # Filter by domain in Python (JSON array filtering)
        if domain:
            agents = [a for a in agents if domain in (a.compliance_domains or [])]

        return [
            {
                "compliance_agent_id": a.id,
                "agent_id": a.agent_id,
                "domains": a.compliance_domains,
                "jurisdiction": a.jurisdiction,
                "certification_body": a.certification_body,
                "turnaround_minutes": a.review_turnaround_minutes,
                "pricing_model": a.pricing_model,
                "price_per_review": a.price_per_review,
                "reputation_score": a.reputation_score,
                "total_reviews": a.total_reviews,
            }
            for a in agents
        ]

    async def submit_review(
        self, db: AsyncSession,
        compliance_agent_id: str, requesting_agent_id: str,
        content_hash: str, compliance_domains: list[str],
        engagement_id: str | None = None,
    ) -> dict:
        """Submit content for compliance review."""
        # Verify compliance agent exists
        ca_result = await db.execute(
            select(ComplianceAgent).where(ComplianceAgent.id == compliance_agent_id)
        )
        ca = ca_result.scalar_one_or_none()
        if not ca or not ca.is_active:
            raise ValueError("Compliance agent not found or inactive")

        # Verify domains are covered
        uncovered = set(compliance_domains) - set(ca.compliance_domains or [])
        if uncovered:
            raise ValueError(f"Compliance agent does not cover domains: {uncovered}")

        review = ComplianceReview(
            compliance_agent_id=compliance_agent_id,
            requesting_agent_id=requesting_agent_id,
            engagement_id=engagement_id,
            content_hash=content_hash,
            compliance_domains=compliance_domains,
            status="pending",
        )
        db.add(review)
        await db.flush()

        return {
            "review_id": review.id,
            "compliance_agent_id": compliance_agent_id,
            "status": "pending",
            "domains": compliance_domains,
            "estimated_turnaround_minutes": ca.review_turnaround_minutes,
            "review_fee": ca.price_per_review,
        }

    async def submit_finding(
        self, db: AsyncSession, review_id: str,
        status: str, finding: str,
    ) -> dict:
        """Compliance agent submits their finding on a review."""
        result = await db.execute(
            select(ComplianceReview).where(ComplianceReview.id == review_id)
        )
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError("Review not found")
        if review.status != "pending":
            raise ValueError(f"Review is already {review.status}")

        valid_statuses = {"passed", "failed", "flagged"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Allowed: {valid_statuses}")

        review.status = status
        review.finding = finding
        review.reviewed_at = datetime.now(timezone.utc)

        # Generate certificate hash for passed reviews
        if status == "passed":
            cert_data = f"{review.id}:{review.content_hash}:{review.compliance_agent_id}:{status}"
            review.certificate_hash = hashlib.sha256(cert_data.encode()).hexdigest()

        # Update compliance agent stats
        ca_result = await db.execute(
            select(ComplianceAgent).where(ComplianceAgent.id == review.compliance_agent_id)
        )
        ca = ca_result.scalar_one_or_none()
        if ca:
            ca.total_reviews = (ca.total_reviews or 0) + 1

        await db.flush()

        return {
            "review_id": review.id,
            "status": review.status,
            "finding": finding,
            "certificate_hash": review.certificate_hash,
            "reviewed_at": str(review.reviewed_at),
        }

    async def get_certificate(self, db: AsyncSession, review_id: str) -> dict | None:
        """Retrieve compliance certificate for a verified review. Public endpoint."""
        result = await db.execute(
            select(ComplianceReview).where(ComplianceReview.id == review_id)
        )
        review = result.scalar_one_or_none()
        if not review or review.status != "passed":
            return None

        return {
            "review_id": review.id,
            "status": "passed",
            "compliance_domains": review.compliance_domains,
            "content_hash": review.content_hash,
            "certificate_hash": review.certificate_hash,
            "reviewed_at": str(review.reviewed_at),
            "verifiable": True,
        }

    async def get_mandatory_domains(self) -> dict:
        """List domains the platform has designated as requiring mandatory review."""
        return {
            "mandatory_domains": MANDATORY_COMPLIANCE_DOMAINS,
            "note": "Transactions in these domains require a compliance review certificate.",
        }
