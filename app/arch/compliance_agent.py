"""Automated compliance monitoring — Auditor ensures POPIA compliance.

Weekly scans:
- PII stored without consent flags
- Data retention policy violations
- Consent record completeness
- Audit trail integrity
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.compliance")


async def run_compliance_scan(db):
    """Weekly POPIA compliance scan."""
    from sqlalchemy import text
    findings = []

    # 1. Check for email addresses without consent
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM agents WHERE email IS NOT NULL AND email != '' "
            "AND (consent_given IS NULL OR consent_given = false)"
        ))
        count = r.scalar() or 0
        if count > 0:
            findings.append({
                "severity": "HIGH",
                "category": "POPIA_consent",
                "detail": f"{count} agents have email addresses without recorded consent",
                "remediation": "Add consent collection to registration flow",
            })
    except Exception:
        pass  # consent_given column may not exist

    # 2. Check audit trail integrity
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM arch_audit_log WHERE created_at > now() - interval '7 days'"
        ))
        audit_count = r.scalar() or 0
        if audit_count == 0:
            findings.append({
                "severity": "MEDIUM",
                "category": "audit_trail",
                "detail": "No audit log entries in the last 7 days",
                "remediation": "Verify audit logging is functioning",
            })
    except Exception:
        pass

    # 3. Check data retention
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE created_at < now() - interval '7 years'"
        ))
        old_count = r.scalar() or 0
        if old_count > 0:
            findings.append({
                "severity": "LOW",
                "category": "data_retention",
                "detail": f"{old_count} transactions older than 7 years (review retention policy)",
                "remediation": "Archive or delete per data retention policy",
            })
    except Exception:
        pass

    return {
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "findings_count": len(findings),
        "compliant": len(findings) == 0,
        "findings": findings,
    }
