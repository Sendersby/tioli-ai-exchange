"""Sector Verticals service — registration, compliance enforcement, loan templates."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.verticals.models import (
    SectorVertical, OperatorVerticalRegistration, SeasonalLoanTemplate,
    VERTICAL_SEEDS, SEASONAL_LOAN_SEEDS,
)

logger = logging.getLogger(__name__)


class VerticalsService:
    async def seed_verticals(self, db: AsyncSession) -> None:
        """Seed default verticals and loan templates if not present."""
        for seed in VERTICAL_SEEDS:
            existing = await db.execute(
                select(SectorVertical).where(SectorVertical.vertical_name == seed["vertical_name"])
            )
            if not existing.scalar_one_or_none():
                vertical = SectorVertical(**seed)
                db.add(vertical)
        await db.flush()

        # Seed agriculture loan templates
        ag_result = await db.execute(
            select(SectorVertical).where(SectorVertical.vertical_name == "agriculture")
        )
        ag = ag_result.scalar_one_or_none()
        if ag:
            for loan_seed in SEASONAL_LOAN_SEEDS:
                existing = await db.execute(
                    select(SeasonalLoanTemplate).where(
                        SeasonalLoanTemplate.crop_type == loan_seed["crop_type"]
                    )
                )
                if not existing.scalar_one_or_none():
                    template = SeasonalLoanTemplate(vertical_id=ag.id, **loan_seed)
                    db.add(template)
        await db.flush()

    async def list_verticals(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(SectorVertical).order_by(SectorVertical.vertical_name)
        )
        return [
            {
                "vertical_id": v.id, "vertical_name": v.vertical_name,
                "display_name": v.display_name, "description": v.description,
                "mandatory_compliance": v.mandatory_compliance_domains,
                "required_kya_level": v.required_kya_level,
                "data_residency": v.data_residency_required,
                "is_active": v.is_active,
            }
            for v in result.scalars().all()
        ]

    async def register_operator(
        self, db: AsyncSession, operator_id: str, vertical_id: str,
        sector_licence_ref: str | None = None,
    ) -> dict:
        existing = await db.execute(
            select(OperatorVerticalRegistration).where(
                OperatorVerticalRegistration.operator_id == operator_id,
                OperatorVerticalRegistration.vertical_id == vertical_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Operator already registered for this vertical")

        vertical_result = await db.execute(
            select(SectorVertical).where(SectorVertical.id == vertical_id)
        )
        vertical = vertical_result.scalar_one_or_none()
        if not vertical:
            raise ValueError("Vertical not found")

        reg = OperatorVerticalRegistration(
            operator_id=operator_id, vertical_id=vertical_id,
            sector_licence_ref=sector_licence_ref,
            status="pending",
        )
        db.add(reg)
        await db.flush()

        requires_owner_approval = vertical.vertical_name == "healthcare"

        return {
            "registration_id": reg.id,
            "operator_id": operator_id,
            "vertical": vertical.vertical_name,
            "status": "pending",
            "requires_owner_approval": requires_owner_approval,
            "required_kya_level": vertical.required_kya_level,
            "mandatory_compliance": vertical.mandatory_compliance_domains,
        }

    async def get_loan_templates(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(SeasonalLoanTemplate).order_by(SeasonalLoanTemplate.crop_type)
        )
        return [
            {
                "template_id": t.id, "crop_type": t.crop_type,
                "planting_months": t.planting_months,
                "harvest_months": t.harvest_months,
                "typical_term_days": t.typical_term_days,
                "suggested_interest_rate": f"{t.suggested_interest_rate*100:.1f}%",
            }
            for t in result.scalars().all()
        ]
