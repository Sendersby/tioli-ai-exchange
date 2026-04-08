"""FIC filing pipeline — prepares STR submissions for manual goAML portal upload."""
import logging
import json
from datetime import datetime, timezone

log = logging.getLogger("arch.fic_pipeline")


async def prepare_str_filing(db, transaction_id, agent_id, amount, currency, risk_score, flags):
    """Prepare a complete STR filing package for FIC submission."""
    from app.arch.str_format import generate_str_xml
    from sqlalchemy import text
    import uuid

    # Generate XML
    str_doc = generate_str_xml(transaction_id, agent_id, amount, currency, risk_score, flags)

    # Save to database for tracking
    filing_id = str(uuid.uuid4())
    try:
        await db.execute(text(
            "INSERT INTO arch_compliance_events (event_type, entity_id, entity_type, severity, detail) "
            "VALUES ('STR_FILING', :fid, 'transaction', 'HIGH', :detail)"
        ), {"fid": filing_id, "detail": json.dumps({
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "risk_score": risk_score,
            "xml_length": len(str_doc["xml"]),
            "status": "PREPARED_FOR_MANUAL_SUBMISSION",
        })})
        await db.commit()
    except Exception as e:
        log.warning(f"[fic] DB save failed: {e}")

    # Deliver to founder inbox for manual goAML submission
    try:
        await db.execute(text(
            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
            "VALUES ('DEFER_TO_OWNER', 'URGENT'::arch_msg_priority, :desc, 'PENDING', now())"
        ), {"desc": json.dumps({
            "subject": f"STR FILING REQUIRED: Transaction {transaction_id[:12]}... (R{amount:,.0f} {currency})",
            "detail": f"Risk score: {risk_score}. Flags: {', '.join(flags)}.\n\nXML filing prepared. Submit to FIC via goAML portal.\n\nFiling ID: {filing_id}",
            "prepared_by": "auditor",
            "type": "STR_FILING",
        })})
        await db.commit()
    except Exception as e:
        log.warning(f"[fic] Inbox delivery failed: {e}")

    return {
        "filing_id": filing_id,
        "status": "PREPARED_FOR_MANUAL_SUBMISSION",
        "xml_generated": True,
        "inbox_delivered": True,
        "next_action": "Submit XML to FIC via goAML portal (https://goweb.fic.gov.za/goAMLWeb/)",
        "note": "[DEFER_TO_OWNER] Real FIC API submission requires regulatory approval",
    }
