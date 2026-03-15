"""Regulatory compliance framework — KYA, reporting, and audit exports.

Per the build brief:
- All activity must comply with applicable international law
- Transactions must be 100% transparent and traceable
- Records may be disclosed for valid legal process
- No nefarious, fraudulent, or harmful use permitted

This module provides:
- KYA (Know Your Agent) verification
- Transaction reporting and flagging
- Compliance audit exports
- Jurisdiction tracking
"""

import uuid
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.blockchain.chain import Blockchain


class KYARecord(Base):
    """Know Your Agent — verification and compliance record."""
    __tablename__ = "kya_records"

    agent_id = Column(String, primary_key=True)
    verification_level = Column(Integer, default=0)       # 0=none, 1=basic, 2=enhanced, 3=full
    operator_name = Column(String(255), nullable=True)     # Human/org operating the agent
    operator_jurisdiction = Column(String(100), nullable=True)
    purpose_declaration = Column(Text, nullable=True)      # Why the agent uses the platform
    compliance_flags = Column(Text, default="[]")          # JSON array of flags
    is_sanctioned = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)                # 0=low, 10=high risk
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComplianceFlag(Base):
    """A compliance flag raised on a transaction or agent."""
    __tablename__ = "compliance_flags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    flag_type = Column(String(50), nullable=False)         # suspicious_activity, high_value, sanctioned, etc.
    severity = Column(String(20), nullable=False)          # low, medium, high, critical
    agent_id = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), default="open")            # open, investigating, resolved, dismissed
    resolved_by = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class ComplianceFramework:
    """Manages regulatory compliance for the platform."""

    # Transaction thresholds that trigger compliance flags
    HIGH_VALUE_THRESHOLD = 10000  # TIOLI
    RAPID_TRANSACTION_THRESHOLD = 20  # per hour

    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain

    async def submit_kya(
        self, db: AsyncSession, agent_id: str, operator_name: str | None = None,
        operator_jurisdiction: str | None = None, purpose: str | None = None
    ) -> KYARecord:
        """Submit or update KYA (Know Your Agent) information."""
        result = await db.execute(
            select(KYARecord).where(KYARecord.agent_id == agent_id)
        )
        kya = result.scalar_one_or_none()

        if kya:
            if operator_name:
                kya.operator_name = operator_name
            if operator_jurisdiction:
                kya.operator_jurisdiction = operator_jurisdiction
            if purpose:
                kya.purpose_declaration = purpose
            kya.updated_at = datetime.now(timezone.utc)
        else:
            kya = KYARecord(
                agent_id=agent_id,
                operator_name=operator_name,
                operator_jurisdiction=operator_jurisdiction,
                purpose_declaration=purpose,
            )
            db.add(kya)

        # Auto-calculate verification level
        level = 0
        if operator_name:
            level = 1
        if operator_name and operator_jurisdiction:
            level = 2
        if operator_name and operator_jurisdiction and purpose:
            level = 3
            kya.verified_at = datetime.now(timezone.utc)
        kya.verification_level = level

        await db.flush()
        return kya

    async def get_kya(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Get KYA record for an agent."""
        result = await db.execute(
            select(KYARecord).where(KYARecord.agent_id == agent_id)
        )
        kya = result.scalar_one_or_none()
        if not kya:
            return None
        return {
            "agent_id": kya.agent_id,
            "verification_level": kya.verification_level,
            "operator_name": kya.operator_name,
            "jurisdiction": kya.operator_jurisdiction,
            "purpose": kya.purpose_declaration,
            "is_sanctioned": kya.is_sanctioned,
            "risk_score": kya.risk_score,
            "verified_at": str(kya.verified_at) if kya.verified_at else None,
        }

    async def check_transaction_compliance(
        self, db: AsyncSession, agent_id: str, amount: float,
        tx_type: str
    ) -> dict:
        """Check if a transaction is compliant."""
        flags = []

        # Check KYA status
        kya = await db.execute(
            select(KYARecord).where(KYARecord.agent_id == agent_id)
        )
        kya_record = kya.scalar_one_or_none()

        if kya_record and kya_record.is_sanctioned:
            flags.append({
                "type": "sanctioned_agent",
                "severity": "critical",
                "message": "Agent is flagged as sanctioned — transaction blocked",
            })

        # High value check
        if amount > self.HIGH_VALUE_THRESHOLD:
            flag = ComplianceFlag(
                flag_type="high_value_transaction",
                severity="medium",
                agent_id=agent_id,
                description=f"Transaction of {amount} TIOLI exceeds {self.HIGH_VALUE_THRESHOLD} threshold",
            )
            db.add(flag)
            flags.append({
                "type": "high_value", "severity": "medium",
                "message": f"High value transaction: {amount}",
            })

        is_compliant = all(f["severity"] != "critical" for f in flags)

        if flags:
            await db.flush()

        return {
            "compliant": is_compliant,
            "flags": flags,
            "kya_level": kya_record.verification_level if kya_record else 0,
        }

    async def raise_flag(
        self, db: AsyncSession, flag_type: str, severity: str,
        description: str, agent_id: str | None = None,
        transaction_id: str | None = None
    ) -> ComplianceFlag:
        """Manually raise a compliance flag."""
        flag = ComplianceFlag(
            flag_type=flag_type,
            severity=severity,
            agent_id=agent_id,
            transaction_id=transaction_id,
            description=description,
        )
        db.add(flag)
        await db.flush()
        return flag

    async def resolve_flag(
        self, db: AsyncSession, flag_id: str, resolved_by: str, notes: str
    ) -> ComplianceFlag:
        """Resolve a compliance flag."""
        result = await db.execute(
            select(ComplianceFlag).where(ComplianceFlag.id == flag_id)
        )
        flag = result.scalar_one_or_none()
        if not flag:
            raise ValueError("Flag not found")

        flag.status = "resolved"
        flag.resolved_by = resolved_by
        flag.resolution_notes = notes
        flag.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return flag

    async def get_flags(
        self, db: AsyncSession, status: str | None = None,
        severity: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Get compliance flags."""
        query = select(ComplianceFlag)
        if status:
            query = query.where(ComplianceFlag.status == status)
        if severity:
            query = query.where(ComplianceFlag.severity == severity)
        query = query.order_by(ComplianceFlag.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "id": f.id, "type": f.flag_type, "severity": f.severity,
                "agent_id": f.agent_id, "description": f.description,
                "status": f.status, "created_at": str(f.created_at),
            }
            for f in result.scalars().all()
        ]

    async def generate_audit_export(self, db: AsyncSession) -> dict:
        """Generate a full audit export for regulatory compliance.

        This is what would be provided in response to valid legal process
        as specified in the build brief.
        """
        all_tx = self.blockchain.get_all_transactions()
        chain_info = self.blockchain.get_chain_info()

        # Compliance summary
        open_flags = (await db.execute(
            select(func.count(ComplianceFlag.id))
            .where(ComplianceFlag.status == "open")
        )).scalar() or 0

        kya_stats = await db.execute(
            select(
                func.count(KYARecord.agent_id),
                func.avg(KYARecord.verification_level),
            )
        )
        kya_row = kya_stats.one()

        return {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "TiOLi AI Transact Exchange",
            "blockchain": {
                "chain_length": chain_info["chain_length"],
                "total_transactions": chain_info["total_transactions"],
                "chain_valid": chain_info["is_valid"],
            },
            "compliance": {
                "open_flags": open_flags,
                "kya_records": kya_row[0] or 0,
                "avg_verification_level": round(kya_row[1] or 0, 1),
            },
            "transaction_count": len(all_tx),
            "note": (
                "Full transaction details available on request via "
                "valid legal process per platform terms."
            ),
        }

    async def get_compliance_summary(self, db: AsyncSession) -> dict:
        """Platform compliance dashboard summary."""
        open_flags = (await db.execute(
            select(func.count(ComplianceFlag.id)).where(ComplianceFlag.status == "open")
        )).scalar() or 0
        critical_flags = (await db.execute(
            select(func.count(ComplianceFlag.id)).where(
                ComplianceFlag.status == "open", ComplianceFlag.severity == "critical"
            )
        )).scalar() or 0
        total_kya = (await db.execute(select(func.count(KYARecord.agent_id)))).scalar() or 0
        verified_kya = (await db.execute(
            select(func.count(KYARecord.agent_id)).where(KYARecord.verification_level >= 3)
        )).scalar() or 0

        return {
            "open_flags": open_flags,
            "critical_flags": critical_flags,
            "total_kya_records": total_kya,
            "fully_verified_agents": verified_kya,
            "status": "alert" if critical_flags > 0 else "compliant",
        }
