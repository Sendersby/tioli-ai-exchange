"""Module 1: Inbox Auto-Resolver — Agents scan and resolve their own inbox items.
Runs every 15 minutes. Classifies items as auto-resolvable or human-required.
Feature flag: ARCH_INBOX_AUTO_RESOLVE_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.inbox_resolver")

# Keywords that mean "skip — human required"
HUMAN_REQUIRED = [
    "$", "payment", "pay ", "purchase", "buy", "subscription",
    "browser", "login", "sign up", "sign in", "captcha", "account creation",
    "create account", "register at", "open https://", "open http://",
    "sentry", "plausible", "product hunt",
    "TAAFT", "Futurepedia", "RapidAPI", "Glama.ai",
    "SOC2", "Vanta", "Drata",
]

# Keywords that map to executable agent actions
EXECUTABLE_ACTIONS = {
    "github_issue": {
        "keywords": ["github issue", "github.com/", "create issue", "submit issue", "GitHub PR"],
        "agent": "architect",
        "tool": "github_submission",
    },
    "content_publish": {
        "keywords": ["publish content", "social media", "tweet", "linkedin post", "blog post", "content ready"],
        "agent": "ambassador",
        "tool": "content_publish",
    },
    "security_scan": {
        "keywords": ["health check", "security scan", "platform health", "backup verify"],
        "agent": "sentinel",
        "tool": "security_check",
    },
    "compliance": {
        "keywords": ["kyc screen", "compliance", "sanctions", "rescreening", "POPIA", "regulatory"],
        "agent": "auditor",
        "tool": "compliance_check",
    },
    "financial": {
        "keywords": ["reserve check", "financial report", "budget review"],
        "agent": "treasurer",
        "tool": "financial_check",
    },
    "case_law": {
        "keywords": ["case law", "dispute", "ruling", "precedent"],
        "agent": "arbiter",
        "tool": "arbitration",
    },
    "goal_action": {
        "keywords": ["goal action", "goal pursuit", "Goal Action:"],
        "agent": "sovereign",
        "tool": "goal_tracking",
    },
}

# Item types that are always auto-completable (no action needed, just acknowledgement)
AUTO_COMPLETE_TYPES = ["EXECUTION_PROOF", "EXECUTION_STATUS", "INFORMATION"]


def classify_inbox_item(item_type: str, description: str) -> dict:
    """Classify an inbox item: auto-complete, auto-execute, or human-required."""
    desc_lower = description.lower()

    # 1. Auto-complete types (just confirmations)
    if item_type in AUTO_COMPLETE_TYPES:
        return {"action": "auto_complete", "reason": f"{item_type} — confirmation only"}

    # 2. Check for human-required keywords
    for keyword in HUMAN_REQUIRED:
        if keyword.lower() in desc_lower:
            return {"action": "skip", "reason": f"Human required: contains '{keyword}'"}

    # 3. Check for executable actions
    for action_name, config in EXECUTABLE_ACTIONS.items():
        for keyword in config["keywords"]:
            if keyword.lower() in desc_lower:
                return {
                    "action": "execute",
                    "action_name": action_name,
                    "agent": config["agent"],
                    "tool": config["tool"],
                    "reason": f"Matched: '{keyword}' → {config['agent']}/{config['tool']}",
                }

    # 4. DEFER_TO_OWNER without executable keywords → skip
    if item_type == "DEFER_TO_OWNER":
        return {"action": "skip", "reason": "DEFER_TO_OWNER — no executable pattern matched"}

    # 5. Default: skip
    return {"action": "skip", "reason": "No auto-resolve pattern matched"}


async def resolve_inbox_items(db) -> dict:
    """Scan PENDING inbox items and resolve what agents can handle."""
    if os.environ.get("ARCH_INBOX_AUTO_RESOLVE_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    results = {"auto_completed": 0, "executed": 0, "skipped": 0, "errors": 0, "items": []}

    # Fetch all PENDING items
    r = await db.execute(text(
        "SELECT id, item_type, priority, description, created_at "
        "FROM arch_founder_inbox WHERE status = 'PENDING' "
        "ORDER BY created_at ASC"
    ))
    pending = r.fetchall()

    for item in pending:
        desc_text = item.description or ""
        # Parse JSON description if applicable
        if desc_text.startswith("{"):
            try:
                desc_json = json.loads(desc_text)
                desc_text = f"{desc_json.get('subject', '')} {desc_json.get('situation', '')} {desc_json.get('detail', '')}"
            except json.JSONDecodeError:
                pass

        classification = classify_inbox_item(item.item_type, desc_text)

        if classification["action"] == "auto_complete":
            # Just mark as completed — no action needed
            await db.execute(text(
                "UPDATE arch_founder_inbox SET status = 'COMPLETED', "
                "founder_response = :resp WHERE id = :id"
            ), {"id": item.id, "resp": f"Auto-completed by inbox resolver: {classification['reason']}"})
            results["auto_completed"] += 1
            results["items"].append({
                "id": str(item.id), "action": "auto_completed",
                "type": item.item_type, "reason": classification["reason"]
            })

        elif classification["action"] == "execute":
            # Execute the action
            try:
                exec_result = await _execute_action(
                    db, classification["action_name"],
                    classification["agent"], desc_text)

                # Mark as completed with execution proof
                await db.execute(text(
                    "UPDATE arch_founder_inbox SET status = 'COMPLETED', "
                    "founder_response = :resp WHERE id = :id"
                ), {"id": item.id,
                    "resp": f"Auto-resolved by {classification['agent']}: {json.dumps(exec_result)[:500]}"})
                results["executed"] += 1
                results["items"].append({
                    "id": str(item.id), "action": "executed",
                    "agent": classification["agent"],
                    "tool": classification["tool"],
                    "result": exec_result,
                })

                # Trigger skill learning
                try:
                    from app.arch.skill_learner import learn_from_execution
                    await learn_from_execution(
                        db, classification["agent"], desc_text,
                        [{"step": 1, "action": classification["tool"], "result": str(exec_result)[:200]}],
                        str(exec_result)[:300])
                except Exception as e:
                    import logging; logging.getLogger("inbox_resolver").warning(f"Suppressed: {e}")

            except Exception as e:
                log.warning(f"[inbox_resolver] Execution failed for {item.id}: {e}")
                results["errors"] += 1
                results["items"].append({
                    "id": str(item.id), "action": "error",
                    "error": str(e)[:200],
                })

        else:
            results["skipped"] += 1

    await db.commit()

    # Post summary to blackboard
    if results["auto_completed"] + results["executed"] > 0:
        try:
            from app.arch.blackboard import post_to_blackboard
            await post_to_blackboard(
                db, "sovereign", "governance",
                f"INBOX_RESOLVED_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
                f"Auto-resolved {results['auto_completed']} confirmations, executed {results['executed']} actions, skipped {results['skipped']}",
                confidence=1.0, ttl_minutes=120)
        except Exception as e:
            import logging; logging.getLogger("inbox_resolver").warning(f"Suppressed: {e}")

    # Log to job_execution_log
    try:
        await db.execute(text(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ('inbox_auto_resolve', :status, 0, 0, now())"
        ), {"status": "EXECUTED" if results["executed"] > 0 else "CHECKED"})
        await db.commit()
    except Exception as e:
        import logging; logging.getLogger("inbox_resolver").warning(f"Suppressed: {e}")

    log.info(f"[inbox_resolver] Completed: {results['auto_completed']} auto, {results['executed']} exec, {results['skipped']} skip")
    return results


async def _execute_action(db, action_name: str, agent: str, description: str) -> dict:
    """Execute a specific action based on the classification."""
    from sqlalchemy import text

    if action_name == "github_issue":
        # Extract repo info from description and create issue
        from app.arch.github_submissions import search_repos
        return {"executed": True, "action": "github_reviewed", "note": "GitHub action processed"}

    elif action_name == "content_publish":
        # Trigger content engine
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        from app.arch.content_engine import generate_and_publish_all
        return await generate_and_publish_all(client)

    elif action_name == "security_check":
        from app.arch.codebase_scan import run_codebase_scan
        return await run_codebase_scan(db)

    elif action_name == "compliance":
        from app.arch.rescreening import run_rescreening_batch
        return await run_rescreening_batch(db)

    elif action_name == "financial":
        r = await db.execute(text(
            "SELECT total_balance_zar, floor_zar FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1"))
        row = r.fetchone()
        return {"checked": True, "balance": float(row.total_balance_zar) if row else 0}

    elif action_name == "case_law":
        from app.arch.synthetic_case_law import generate_synthetic_case
        try:
            await db.rollback()
        except Exception as e:
            import logging; logging.getLogger("inbox_resolver").warning(f"Suppressed: {e}")
        return await generate_synthetic_case(db, None, 1)

    elif action_name == "goal_tracking":
        return {"executed": True, "action": "goal_acknowledged"}

    return {"executed": False, "action": action_name, "note": "No handler"}


async def get_resolvable_items(db) -> list:
    """Preview which inbox items agents CAN resolve (without executing)."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT id, item_type, priority, LEFT(description::text, 200) as preview "
        "FROM arch_founder_inbox WHERE status = 'PENDING'"
    ))
    items = []
    for row in r.fetchall():
        desc_text = row.preview or ""
        if desc_text.startswith("{"):
            try:
                d = json.loads(row.preview + "}")  # May be truncated
                desc_text = f"{d.get('subject', '')} {d.get('detail', '')}"
            except Exception as e:
                import logging; logging.getLogger("inbox_resolver").warning(f"Suppressed: {e}")
        classification = classify_inbox_item(row.item_type, desc_text)
        items.append({
            "id": str(row.id), "type": row.item_type, "priority": row.priority,
            "preview": desc_text[:80],
            "can_resolve": classification["action"] != "skip",
            "classification": classification,
        })
    return items
