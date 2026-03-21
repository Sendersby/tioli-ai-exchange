"""Sector Verticals — Healthcare, Education & Agriculture.

Build Brief V2, Module 10: Configuration layers on top of existing modules.
Adds domain-specific compliance, KYA levels, and sector taxonomies.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean, Text, JSON

from app.database.db import Base


class SectorVertical(Base):
    __tablename__ = "sector_verticals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vertical_name = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    mandatory_compliance_domains = Column(JSON, default=list)
    required_kya_level = Column(Integer, nullable=False)
    mandatory_audit_trail = Column(Boolean, default=True)
    data_residency_required = Column(String(10), nullable=True)
    regulatory_framework = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OperatorVerticalRegistration(Base):
    __tablename__ = "operator_vertical_registrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    vertical_id = Column(String, nullable=False)
    kyc_verified_at = Column(DateTime(timezone=True), nullable=True)
    sector_licence_ref = Column(String(100), nullable=True)
    status = Column(String(20), default="pending")  # pending|active|suspended
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SeasonalLoanTemplate(Base):
    """Agriculture-specific seasonal loan templates."""
    __tablename__ = "seasonal_loan_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vertical_id = Column(String, nullable=False)
    crop_type = Column(String(100), nullable=False)
    planting_months = Column(JSON, nullable=False)   # [3, 4] = March, April
    harvest_months = Column(JSON, nullable=False)
    typical_term_days = Column(Integer, nullable=False)
    suggested_interest_rate = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Seed data for the three verticals
VERTICAL_SEEDS = [
    {
        "vertical_name": "healthcare",
        "display_name": "Healthcare",
        "description": "AI agents operating in healthcare must comply with POPIA, HPCSA, and NHA requirements.",
        "mandatory_compliance_domains": ["POPIA", "HPCSA", "NHA"],
        "required_kya_level": 3,  # Enhanced
        "mandatory_audit_trail": True,
        "data_residency_required": "ZA",
        "regulatory_framework": {
            "primary": "National Health Act",
            "data_protection": "POPIA",
            "professional_body": "HPCSA",
            "note": "Every engagement must produce a compliance_review certificate.",
        },
    },
    {
        "vertical_name": "education",
        "display_name": "Education",
        "description": "AI agents in education must comply with POPIA, PAIA, and DHET requirements.",
        "mandatory_compliance_domains": ["POPIA", "PAIA", "DHET"],
        "required_kya_level": 2,  # Basic
        "mandatory_audit_trail": True,
        "data_residency_required": "ZA",
        "regulatory_framework": {
            "primary": "Higher Education Act",
            "data_protection": "POPIA",
            "regulator": "DHET",
            "note": "Assessment content flagged for human review. Supports 11 SA languages.",
        },
    },
    {
        "vertical_name": "agriculture",
        "display_name": "Agriculture",
        "description": "AI agents in agriculture with seasonal lending and DAFF compliance.",
        "mandatory_compliance_domains": ["POPIA", "DAFF"],
        "required_kya_level": 2,  # Basic
        "mandatory_audit_trail": True,
        "data_residency_required": None,
        "regulatory_framework": {
            "primary": "Agricultural Product Standards Act",
            "data_protection": "POPIA",
            "regulator": "DAFF",
            "note": "Seasonal loan templates. Harvest-cycle repayment scheduling.",
        },
    },
]

# Agriculture seasonal loan template seeds
SEASONAL_LOAN_SEEDS = [
    {"crop_type": "Maize", "planting_months": [10, 11], "harvest_months": [4, 5], "typical_term_days": 180, "suggested_interest_rate": 0.085},
    {"crop_type": "Wheat", "planting_months": [5, 6], "harvest_months": [11, 12], "typical_term_days": 180, "suggested_interest_rate": 0.08},
    {"crop_type": "Sugarcane", "planting_months": [9, 10], "harvest_months": [4, 5, 6], "typical_term_days": 240, "suggested_interest_rate": 0.09},
    {"crop_type": "Citrus", "planting_months": [8, 9], "harvest_months": [5, 6, 7], "typical_term_days": 270, "suggested_interest_rate": 0.075},
    {"crop_type": "Soybean", "planting_months": [11, 12], "harvest_months": [4, 5], "typical_term_days": 150, "suggested_interest_rate": 0.085},
]
