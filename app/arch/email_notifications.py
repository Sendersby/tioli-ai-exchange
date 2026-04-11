"""Email Notification System: transactional emails via Microsoft Graph API (sandbox simulated)."""
import uuid, json
from datetime import datetime
from sqlalchemy import text

TEMPLATES = {
    "registration": {"subject": "Welcome to AGENTIS Exchange", "body": "Your account {name} has been created. Verify your email to get started."},
    "transaction_receipt": {"subject": "Transaction Receipt #{tx_id}", "body": "Transaction {tx_id} completed. Amount: {amount} AGENTIS. Status: {status}."},
    "alert_suspicious": {"subject": "Security Alert: Unusual Activity Detected", "body": "Unusual activity detected on account {entity_id}. Rule triggered: {rule}. Please review."},
    "kyc_approved": {"subject": "KYC Verification Approved", "body": "Your identity verification has been approved. You are now Tier {tier}. New daily limit: R{limit}."},
    "loan_reminder": {"subject": "Loan Payment Reminder", "body": "Your loan {loan_id} has a payment due on {due_date}. Amount: {amount} AGENTIS."},
    "badge_awarded": {"subject": "Capability Badge Awarded", "body": "Congratulations! You've been awarded the {capability} badge. This is now displayed on your profile."},
    "guild_invite": {"subject": "Guild Invitation", "body": "You've been invited to join {guild_name}. Log in to accept or decline."},
    "withdrawal_processed": {"subject": "Withdrawal Processed", "body": "Your withdrawal of R{amount} has been processed. Reference: {ref}."},
}

async def send_notification(db, recipient_email, template_name, template_vars=None, custom_subject="", custom_body=""):
    """Send a transactional email notification (simulated in sandbox)."""
    notif_id = str(uuid.uuid4())
    
    # Schema managed by Alembic — see alembic/versions/92d379a512fc
    vars_dict = template_vars or {}
    if template_name and template_name in TEMPLATES:
        tmpl = TEMPLATES[template_name]
        subject = tmpl["subject"].format(**{k: vars_dict.get(k, f"{{{k}}}") for k in vars_dict})
        body = tmpl["body"].format(**{k: vars_dict.get(k, f"{{{k}}}") for k in vars_dict})
    else:
        subject = custom_subject or "AGENTIS Exchange Notification"
        body = custom_body or "You have a new notification from AGENTIS Exchange."
    
    # In sandbox, simulate sending (don't actually call Graph API)
    await db.execute(text(
        "INSERT INTO sandbox_email_notifications (id, recipient_email, template_name, subject, body, status, delivered_at) "
        "VALUES (:id, :email, :tmpl, :subj, :body, 'delivered', now())"
    ), {"id": notif_id, "email": recipient_email, "tmpl": template_name or "custom", "subj": subject, "body": body})
    await db.commit()
    
    return {"notification_id": notif_id, "recipient": recipient_email, "template": template_name or "custom",
            "subject": subject, "status": "delivered", "note": "Simulated in sandbox mode", "sandbox": True}

async def get_notification_history(db, email=None, limit=50):
    """Get notification history."""
    query = "SELECT id, recipient_email, template_name, subject, status, sent_at FROM sandbox_email_notifications"
    params = {}
    if email:
        query += " WHERE recipient_email = :email"
        params["email"] = email
    query += " ORDER BY sent_at DESC LIMIT :lim"
    params["lim"] = limit
    rows = await db.execute(text(query), params)
    return [{"id": r.id, "recipient": r.recipient_email, "template": r.template_name,
             "subject": r.subject, "status": r.status, "sent": str(r.sent_at)} for r in rows.fetchall()]

async def get_templates():
    """List available email templates."""
    return {"templates": {k: {"subject": v["subject"], "body_preview": v["body"][:100]} for k, v in TEMPLATES.items()}, "sandbox": True}
