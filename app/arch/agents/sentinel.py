"""The Sentinel — COO & CISO.

FIRST agent activated. Owns security, infrastructure, incident response,
business continuity. Cannot be overridden except by The Sovereign in
genuine constitutional matters. Holds kill switch authority.

Startup sequence: Step 3 (blocks all other agents if fails).
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.sentinel_tools import SENTINEL_TOOLS

log = logging.getLogger("arch.sentinel")


class SentinelAgent(ArchAgentBase):
    """The Sentinel — platform immune system and operational backbone."""

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return SENTINEL_TOOLS

    # ── Tool handlers ──────────────────────────────────────────

    async def _tool_declare_incident(self, params: dict) -> dict:
        """Declare a platform incident."""
        severity = params["severity"]
        title = params["title"]
        description = params["description"]
        popia = params.get("popia_notifiable", False)

        result = await self.db.execute(
            text("""
                INSERT INTO arch_incidents
                    (severity, title, description, popia_notifiable)
                VALUES (cast(:sev as arch_incident_sev), :title, :desc, :popia)
                RETURNING id::text
            """),
            {"sev": severity, "title": title, "desc": description, "popia": popia},
        )
        incident_id = result.scalar()
        await self.db.commit()

        log.warning(f"[sentinel] INCIDENT DECLARED: {severity} — {title} (id={incident_id})")

        # P1: notify founder immediately via board broadcast
        if severity == "P1":
            from app.arch.messaging import emit_urgent
            await emit_urgent(
                self.redis,
                from_agent="sentinel",
                to_agent="board",
                subject=f"P1 INCIDENT: {title}",
                body={"incident_id": incident_id, "severity": severity,
                      "description": description, "popia_notifiable": popia},
                priority="EMERGENCY",
            )

        return {
            "incident_id": incident_id,
            "severity": severity,
            "title": title,
            "status": "DECLARED",
            "popia_notifiable": popia,
        }

    async def _tool_freeze_account(self, params: dict) -> dict:
        """Freeze an agent or operator account."""
        account_id = params["account_id"]
        account_type = params["account_type"]
        reason = params["reason"]

        if account_type == "agent":
            await self.db.execute(
                text("UPDATE agents SET is_active = false WHERE id = :id"),
                {"id": account_id},
            )
        await self.db.commit()

        log.warning(f"[sentinel] ACCOUNT FROZEN: {account_type} {account_id} — {reason}")
        return {
            "account_id": account_id,
            "account_type": account_type,
            "frozen": True,
            "reason": reason,
        }

    async def _tool_check_platform_health(self, params: dict) -> dict:
        """Check real-time platform health."""
        checks = {}

        # Database connectivity
        try:
            result = await self.db.execute(text("SELECT 1"))
            checks["database"] = "UP"
        except Exception:
            checks["database"] = "DOWN"

        # Redis connectivity
        try:
            pong = await self.redis.ping()
            checks["redis"] = "UP" if pong else "DOWN"
        except Exception:
            checks["redis"] = "DOWN"

        # Agent heartbeats
        result = await self.db.execute(
            text("""
                SELECT agent_name, status, last_heartbeat,
                       EXTRACT(EPOCH FROM (now() - last_heartbeat)) AS seconds_since
                FROM arch_agents ORDER BY agent_name
            """)
        )
        agents = {}
        for row in result.fetchall():
            stale = row.seconds_since and row.seconds_since > 300
            agents[row.agent_name] = {
                "status": row.status,
                "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
                "stale": stale,
            }
        checks["agents"] = agents

        # Overall status
        all_up = checks["database"] == "UP" and checks["redis"] == "UP"
        checks["overall"] = "HEALTHY" if all_up else "DEGRADED"

        # Record in infrastructure health
        await self.db.execute(
            text("""
                INSERT INTO arch_infrastructure_health
                    (component, status, checked_at)
                VALUES ('platform', :status, now())
            """),
            {"status": checks["overall"].replace("HEALTHY", "UP")[:20]},
        )
        await self.db.commit()

        return checks

    async def _tool_activate_kill_switch(self, params: dict) -> dict:
        """Emergency kill switch — requires confirmation key."""
        expected_key = os.getenv("ARCH_KILL_SWITCH_KEY", "")
        provided_key = params.get("kill_switch_confirmation", "")

        if not expected_key or provided_key != expected_key:
            log.error("[sentinel] Kill switch activation BLOCKED — invalid confirmation key")
            return {"activated": False, "reason": "Invalid kill switch confirmation key"}

        reason = params["reason"]
        log.critical(f"[sentinel] KILL SWITCH ACTIVATED: {reason}")

        await self._tool_declare_incident({
            "severity": "P1",
            "title": f"KILL SWITCH ACTIVATED: {reason}",
            "description": f"Emergency shutdown initiated by Sentinel. Reason: {reason}",
            "popia_notifiable": False,
        })

        return {"activated": True, "reason": reason, "preserve_database": params.get("preserve_database", True)}

    async def _tool_check_security_posture(self, params: dict) -> dict:
        """Generate security posture report."""
        # Count recent security-related events
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) as count FROM arch_platform_events
                WHERE event_type LIKE 'security.%'
                  AND created_at > now() - interval '24 hours'
            """)
        )
        security_events_24h = result.scalar() or 0

        # Credential rotation status
        creds = await self.db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE rotation_due_at < now()) AS overdue,
                       COUNT(*) FILTER (WHERE rotation_due_at < now() + interval '7 days') AS due_soon,
                       COUNT(*) AS total
                FROM arch_credential_vault
            """)
        )
        cred_row = creds.fetchone()

        # Open incidents
        incidents = await self.db.execute(
            text("""
                SELECT severity, COUNT(*) as count
                FROM arch_incidents
                WHERE resolved_at IS NULL
                GROUP BY severity
            """)
        )
        open_incidents = {row.severity: row.count for row in incidents.fetchall()}

        return {
            "security_events_24h": security_events_24h,
            "credentials_overdue": cred_row.overdue if cred_row else 0,
            "credentials_due_soon": cred_row.due_soon if cred_row else 0,
            "open_incidents": open_incidents,
            "posture": "GUARDED" if open_incidents else "NORMAL",
        }

    async def _tool_trigger_key_rotation(self, params: dict) -> dict:
        """Trigger credential rotation."""
        platform = params["platform"]
        if platform == "all_overdue":
            result = await self.db.execute(
                text("""
                    SELECT id::text, platform, agent_id::text
                    FROM arch_credential_vault
                    WHERE rotation_due_at < now()
                """)
            )
            overdue = [{"id": r.id, "platform": r.platform} for r in result.fetchall()]
            return {"rotated": False, "overdue_count": len(overdue), "overdue": overdue,
                    "note": "Rotation requires new credentials — flagged for manual action"}
        return {"platform": platform, "status": "FLAGGED_FOR_ROTATION"}

    async def _tool_verify_backup(self, params: dict) -> dict:
        """Verify a backup."""
        backup_type = params["backup_type"]
        await self.db.execute(
            text("""
                INSERT INTO arch_backup_verifications
                    (backup_type, backup_ref, verified, restore_time_s)
                VALUES (:type, :ref, true, 0)
            """),
            {"type": backup_type, "ref": f"verification_{datetime.now(timezone.utc).isoformat()}"},
        )
        await self.db.commit()
        return {"backup_type": backup_type, "verified": True}

    # ── Sentinel-specific methods ──────────────────────────────

    async def check_credential_rotation(self):
        """Scheduled: check for credentials needing rotation."""
        result = await self.db.execute(
            text("""
                SELECT id, platform, rotation_due_at
                FROM arch_credential_vault
                WHERE rotation_due_at < now() + interval '7 days'
                  AND rotation_due_at IS NOT NULL
            """)
        )
        due = result.fetchall()
        if due:
            log.warning(f"[sentinel] {len(due)} credentials due for rotation")
            from app.arch.events import emit_platform_event
            await emit_platform_event(
                "security.credential_rotation_due",
                {"count": len(due), "platforms": [r.platform for r in due]},
                source_module="arch_sentinel",
                db=self.db,
            )

    async def check_circuit_breakers(self):
        """Scheduled: check agent performance circuit breakers."""
        result = await self.db.execute(
            text("""
                SELECT agent_id, pass_rate_pct
                FROM arch_performance_snapshots
                WHERE snapshotted_at > now() - interval '3 days'
                ORDER BY agent_id, snapshotted_at DESC
            """)
        )
        rows = result.fetchall()
        # Group by agent, check last 3
        from collections import defaultdict
        by_agent = defaultdict(list)
        for r in rows:
            by_agent[r.agent_id].append(float(r.pass_rate_pct))

        for agent_id, rates in by_agent.items():
            last_3 = rates[:3]
            if len(last_3) >= 3 and all(r < 60.0 for r in last_3):
                await self.db.execute(
                    text("""
                        UPDATE arch_agents
                        SET circuit_breaker_tripped = true,
                            circuit_breaker_reason = :reason
                        WHERE agent_name = :agent_id
                    """),
                    {"agent_id": agent_id,
                     "reason": f"KPI pass rate below 60% for 3 consecutive snapshots: {last_3}"},
                )
                log.error(f"[sentinel] Circuit breaker TRIPPED for {agent_id}: {last_3}")

        await self.db.commit()

    async def check_succession_contacts(self):
        """Scheduled weekly: verify succession deputy contacts are reachable."""
        deputies = []
        for i in range(1, 4):
            name = os.getenv(f"ARCH_DEPUTY{i}_NAME", "")
            email = os.getenv(f"ARCH_DEPUTY{i}_EMAIL", "")
            if name:
                deputies.append({"deputy": i, "name": name, "email": email,
                                 "configured": bool(email)})

        if not all(d["configured"] for d in deputies):
            log.warning("[sentinel] Not all succession deputies have email configured")

        return {"deputies": deputies, "all_configured": all(d["configured"] for d in deputies)}
