"""Financial audit trail logging — L-006 remediation."""
import hashlib
import json
import uuid
import logging
from datetime import datetime
from sqlalchemy import text

log = logging.getLogger("audit.financial")

VALID_EVENTS = {
    'TRADE_EXECUTED', 'COMMISSION_CHARGED', 'ESCROW_LOCKED', 'ESCROW_RELEASED',
    'WITHDRAWAL_INITIATED', 'DEPOSIT_CONFIRMED', 'REFUND_ISSUED', 'DISPUTE_RAISED',
    'DISPUTE_RESOLVED', 'REVENUE_RECORDED', 'ORDER_PLACED', 'ORDER_CANCELLED',
    'BALANCE_TRANSFER', 'SUBSCRIPTION_ACTIVATED', 'SUBSCRIPTION_CANCELLED',
    'ESCROW_REFUNDED', 'DISPUTE_ESCALATED', 'KYC_CHECK_PASSED', 'KYC_CHECK_BLOCKED',
    'FIAT_DEPOSIT', 'FIAT_WITHDRAWAL',
}


async def log_financial_event(db, event_type, actor_id=None, actor_type='system',
                               target_id=None, target_type=None, amount=None,
                               currency=None, before_state=None, after_state=None,
                               ip_address=None, session_id=None):
    """Write an immutable audit trail entry with integrity hash."""
    if event_type not in VALID_EVENTS:
        log.warning(f"Unknown audit event type: {event_type}")
        return None

    entry_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Compute integrity hash (tamper-evident)
    hash_input = f"{entry_id}|{now}|{event_type}|{actor_id}|{target_id}|{amount}|{currency}"
    integrity_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    try:
        await db.execute(text(
            "INSERT INTO financial_audit_log "
            "(id, created_at, event_type, actor_id, actor_type, target_id, target_type, "
            "amount, currency, before_state, after_state, ip_address, session_id, integrity_hash) "
            "VALUES (:id, now(), :evt, :actor, :atype, :target, :ttype, "
            ":amt, :cur, cast(:before as jsonb), cast(:after as jsonb), :ip, :sess, :hash)"
        ), {
            "id": entry_id, "evt": event_type, "actor": actor_id, "atype": actor_type,
            "target": target_id, "ttype": target_type,
            "amt": float(amount) if amount is not None else None,
            "cur": currency,
            "before": json.dumps(before_state) if before_state else None,
            "after": json.dumps(after_state) if after_state else None,
            "ip": ip_address, "sess": session_id, "hash": integrity_hash,
        })
        log.info(f"Audit: {event_type} actor={actor_id} amount={amount} {currency}")
    except Exception as e:
        log.error(f"Failed to write audit log: {e}")
        return None
    return entry_id
