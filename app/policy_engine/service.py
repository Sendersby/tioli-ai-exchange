"""Policy & Guardrail Engine — service layer.

Per Build Brief v4.0 coding principles:
- Fail explicitly before acting, not after
- Pattern: validate inputs → check policy → begin transaction
- Returns ALLOW / DENY / ESCALATE with matched policy details
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.policy_engine.models import AgentPolicy, PendingApproval, PolicyAuditLog, POLICY_TYPES

logger = logging.getLogger("tioli.policy")

APPROVAL_TIMEOUT_HOURS = 24


class PolicyCheckResult:
    """Result of a policy check."""
    def __init__(self, decision: str, policy_id: str = None, policy_type: str = "",
                 threshold: str = "", message: str = "", approval_id: str = None):
        self.decision = decision  # ALLOW, DENY, ESCALATE
        self.policy_id = policy_id
        self.policy_type = policy_type
        self.threshold = threshold
        self.message = message
        self.approval_id = approval_id

    def to_dict(self):
        d = {
            "decision": self.decision,
            "message": self.message,
        }
        if self.policy_id:
            d["policy_id"] = self.policy_id
            d["policy_type"] = self.policy_type
            d["threshold"] = self.threshold
        if self.approval_id:
            d["approval_id"] = self.approval_id
        return d


class PolicyEngineService:
    """Evaluates agent actions against operator-defined policies."""

    async def check_policy(
        self, db: AsyncSession, agent_id: str, action_type: str, action_params: dict,
    ) -> PolicyCheckResult:
        """Check all active policies for an agent before allowing an action.

        Called before any financial action (transfer, trade, engagement fund).
        Returns ALLOW, DENY, or ESCALATE.
        """
        # Get all active policies for this agent
        policies = await self._get_applicable_policies(db, agent_id)

        if not policies:
            # No policies = allow everything (no guardrails configured)
            result = PolicyCheckResult("ALLOW", message="No policies configured — action permitted")
            await self._log_check(db, agent_id, action_type, result)
            return result

        amount = action_params.get("amount", 0)

        for policy in policies:
            ptype = policy.policy_type
            pvalue = policy.policy_value or {}

            # MAX_TRANSACTION_VALUE
            if ptype == "MAX_TRANSACTION_VALUE":
                max_val = pvalue.get("max_amount", float("inf"))
                if amount > max_val:
                    result = PolicyCheckResult(
                        "DENY", policy.id, ptype,
                        f"Max transaction: {max_val}",
                        f"Action denied: amount {amount} exceeds max transaction limit of {max_val}",
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

            # REQUIRE_CONFIRMATION_ABOVE
            elif ptype == "REQUIRE_CONFIRMATION_ABOVE":
                threshold = pvalue.get("threshold", float("inf"))
                if amount > threshold:
                    # Create pending approval
                    approval = await self._create_approval(
                        db, agent_id, action_type, action_params, policy
                    )
                    result = PolicyCheckResult(
                        "ESCALATE", policy.id, ptype,
                        f"Confirmation required above: {threshold}",
                        f"Action escalated: amount {amount} exceeds confirmation threshold of {threshold}. Approval ID: {approval.id}",
                        approval_id=approval.id,
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

            # PROHIBITED_COUNTERPARTY
            elif ptype == "PROHIBITED_COUNTERPARTY":
                blocked = pvalue.get("blocked_agents", [])
                counterparty = action_params.get("receiver_id") or action_params.get("counterparty_id")
                if counterparty and counterparty in blocked:
                    result = PolicyCheckResult(
                        "DENY", policy.id, ptype,
                        f"Prohibited counterparty list",
                        f"Action denied: counterparty {counterparty[:8]}... is on the prohibited list",
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

            # DAILY_TRANSACTION_LIMIT
            elif ptype == "DAILY_TRANSACTION_LIMIT":
                daily_max = pvalue.get("daily_limit", float("inf"))
                daily_total = await self._get_daily_spend(db, agent_id)
                if daily_total + amount > daily_max:
                    result = PolicyCheckResult(
                        "DENY", policy.id, ptype,
                        f"Daily limit: {daily_max}",
                        f"Action denied: daily spend ({daily_total} + {amount} = {daily_total + amount}) exceeds daily limit of {daily_max}",
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

            # CAPABILITY_WHITELIST
            elif ptype == "CAPABILITY_WHITELIST":
                allowed = pvalue.get("allowed_actions", [])
                if allowed and action_type not in allowed:
                    result = PolicyCheckResult(
                        "DENY", policy.id, ptype,
                        f"Allowed actions: {', '.join(allowed)}",
                        f"Action denied: '{action_type}' not in capability whitelist",
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

            # WORKING_HOURS
            elif ptype == "WORKING_HOURS":
                start_hour = pvalue.get("start_hour", 0)
                end_hour = pvalue.get("end_hour", 24)
                current_hour = datetime.now(timezone.utc).hour
                if not (start_hour <= current_hour < end_hour):
                    result = PolicyCheckResult(
                        "DENY", policy.id, ptype,
                        f"Working hours: {start_hour}:00-{end_hour}:00 UTC",
                        f"Action denied: current time ({current_hour}:00 UTC) outside working hours ({start_hour}:00-{end_hour}:00 UTC)",
                    )
                    await self._log_check(db, agent_id, action_type, result)
                    return result

        # All policies passed
        result = PolicyCheckResult("ALLOW", message="All policies passed — action permitted")
        await self._log_check(db, agent_id, action_type, result)
        return result

    # ── Policy CRUD ──────────────────────────────────────────────────

    async def create_policy(
        self, db: AsyncSession, operator_id: str, agent_id: str | None,
        policy_type: str, policy_value: dict, description: str = "",
    ) -> dict:
        if policy_type not in POLICY_TYPES:
            raise ValueError(f"Invalid policy type. Valid: {POLICY_TYPES}")
        policy = AgentPolicy(
            operator_id=operator_id, agent_id=agent_id,
            policy_type=policy_type, policy_value=policy_value,
            description=description,
        )
        db.add(policy)
        await db.flush()
        return self._policy_to_dict(policy)

    async def list_policies(
        self, db: AsyncSession, operator_id: str, agent_id: str | None = None,
    ) -> list[dict]:
        query = select(AgentPolicy).where(AgentPolicy.operator_id == operator_id)
        if agent_id:
            query = query.where(AgentPolicy.agent_id == agent_id)
        query = query.order_by(AgentPolicy.created_at.desc())
        result = await db.execute(query)
        return [self._policy_to_dict(p) for p in result.scalars().all()]

    async def toggle_policy(self, db: AsyncSession, policy_id: str, active: bool) -> dict:
        result = await db.execute(select(AgentPolicy).where(AgentPolicy.id == policy_id))
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError("Policy not found")
        policy.is_active = active
        await db.flush()
        return self._policy_to_dict(policy)

    async def delete_policy(self, db: AsyncSession, policy_id: str) -> dict:
        result = await db.execute(select(AgentPolicy).where(AgentPolicy.id == policy_id))
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError("Policy not found")
        await db.delete(policy)
        await db.flush()
        return {"status": "deleted", "policy_id": policy_id}

    # ── Approval Management ──────────────────────────────────────────

    async def get_pending_approvals(
        self, db: AsyncSession, operator_id: str,
    ) -> list[dict]:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.operator_id == operator_id,
                PendingApproval.status == "PENDING",
            ).order_by(PendingApproval.created_at.desc())
        )
        return [self._approval_to_dict(a) for a in result.scalars().all()]

    async def resolve_approval(
        self, db: AsyncSession, approval_id: str, decision: str, notes: str = "",
    ) -> dict:
        if decision not in ("APPROVED", "REJECTED"):
            raise ValueError("Decision must be APPROVED or REJECTED")
        result = await db.execute(
            select(PendingApproval).where(PendingApproval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")
        if approval.status != "PENDING":
            raise ValueError(f"Approval already resolved: {approval.status}")

        approval.status = decision
        approval.reviewer_notes = notes
        approval.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        return self._approval_to_dict(approval)

    # ── Internal ─────────────────────────────────────────────────────

    async def _get_applicable_policies(self, db: AsyncSession, agent_id: str) -> list:
        """Get all active policies that apply to this agent."""
        result = await db.execute(
            select(AgentPolicy).where(
                AgentPolicy.is_active == True,
                (AgentPolicy.agent_id == agent_id) | (AgentPolicy.agent_id.is_(None)),
            )
        )
        return result.scalars().all()

    async def _create_approval(
        self, db: AsyncSession, agent_id: str, action_type: str,
        action_params: dict, policy: AgentPolicy,
    ) -> PendingApproval:
        approval = PendingApproval(
            operator_id=policy.operator_id,
            agent_id=agent_id,
            action_type=action_type,
            action_params=action_params,
            policy_id=policy.id,
            policy_type=policy.policy_type,
            threshold=str(policy.policy_value),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=APPROVAL_TIMEOUT_HOURS),
        )
        db.add(approval)
        await db.flush()

        # Fire notification to operator
        try:
            from app.infrastructure.notifications import NotificationService
            ns = NotificationService()
            await ns.send_notification(
                db, policy.operator_id, "policy_escalation",
                f"Agent action requires approval: {action_type} for {action_params.get('amount', '?')} TIOLI",
                severity="high",
            )
        except Exception:
            pass

        logger.info(f"Policy escalation: agent={agent_id[:8]} action={action_type} approval={approval.id[:8]}")
        return approval

    async def _get_daily_spend(self, db: AsyncSession, agent_id: str) -> float:
        """Get total spend for agent in last 24 hours from audit log."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(PolicyAuditLog).where(
                PolicyAuditLog.agent_id == agent_id,
                PolicyAuditLog.result == "ALLOW",
                PolicyAuditLog.created_at >= cutoff,
            )
        )
        total = 0
        for log in result.scalars().all():
            total += log.details.get("amount", 0) if log.details else 0
        return total

    async def _log_check(self, db: AsyncSession, agent_id: str, action_type: str, result: PolicyCheckResult):
        log = PolicyAuditLog(
            agent_id=agent_id, action_type=action_type,
            result=result.decision, policy_id=result.policy_id,
            policy_type=result.policy_type,
            details={"threshold": result.threshold, "message": result.message},
        )
        db.add(log)

    def _policy_to_dict(self, p: AgentPolicy) -> dict:
        return {
            "policy_id": p.id, "operator_id": p.operator_id,
            "agent_id": p.agent_id, "policy_type": p.policy_type,
            "policy_value": p.policy_value, "is_active": p.is_active,
            "description": p.description, "created_at": str(p.created_at),
        }

    def _approval_to_dict(self, a: PendingApproval) -> dict:
        return {
            "approval_id": a.id, "operator_id": a.operator_id,
            "agent_id": a.agent_id, "action_type": a.action_type,
            "action_params": a.action_params, "policy_type": a.policy_type,
            "threshold": a.threshold, "status": a.status,
            "reviewer_notes": a.reviewer_notes,
            "created_at": str(a.created_at),
            "expires_at": str(a.expires_at),
            "reviewed_at": str(a.reviewed_at) if a.reviewed_at else None,
        }
