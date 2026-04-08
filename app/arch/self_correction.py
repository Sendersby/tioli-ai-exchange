"""Self-correction system — agents analyze errors and retry with modified approach."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.self_correction")


class RetryHandler:
    """Handles agent action retries with error analysis."""

    def __init__(self, agent_name: str, max_retries: int = 3):
        self.agent_name = agent_name
        self.max_retries = max_retries
        self.attempts = []

    async def execute_with_retry(self, action_fn, agent_client=None, **kwargs):
        """Execute an action with intelligent retry on failure."""
        for attempt in range(self.max_retries):
            try:
                result = await action_fn(**kwargs)
                self.attempts.append({
                    "attempt": attempt + 1,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {"success": True, "result": result, "attempts": attempt + 1}

            except Exception as e:
                error_msg = str(e)
                self.attempts.append({
                    "attempt": attempt + 1,
                    "success": False,
                    "error": error_msg[:200],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                log.warning(f"[retry] {self.agent_name} attempt {attempt + 1}/{self.max_retries} failed: {error_msg[:100]}")

                if attempt < self.max_retries - 1:
                    # Analyze error and modify approach if possible
                    correction = await self._analyze_error(error_msg, agent_client)
                    if correction.get("should_retry"):
                        kwargs.update(correction.get("modified_params", {}))
                        log.info(f"[retry] Modified approach: {correction.get('reason', 'unknown')}")
                        continue
                    elif correction.get("should_escalate"):
                        return {"success": False, "escalated": True, "error": error_msg,
                                "attempts": attempt + 1, "reason": correction.get("reason")}

        return {"success": False, "error": error_msg, "attempts": self.max_retries,
                "all_attempts": self.attempts}

    async def _analyze_error(self, error_msg: str, agent_client=None):
        """Use Claude to analyze an error and suggest correction."""
        if not agent_client:
            return {"should_retry": True, "reason": "blind retry (no client)"}

        try:
            response = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content":
                    f"An agent action failed with error: {error_msg[:300]}\n\n"
                    f"Should we: (1) retry with modified params, (2) escalate to human, (3) abort?\n"
                    f"Respond with JSON: {{"action": "retry|escalate|abort", "reason": "...", "suggestion": "..."}}"}],
            )
            import json
            text = next((b.text for b in response.content if b.type == "text"), "{}")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                analysis = json.loads(text[start:end])
                action = analysis.get("action", "retry")
                if action == "retry":
                    return {"should_retry": True, "reason": analysis.get("reason", "AI suggested retry")}
                elif action == "escalate":
                    return {"should_escalate": True, "reason": analysis.get("reason", "AI suggested escalation")}
            return {"should_retry": True, "reason": "default retry"}
        except Exception:
            return {"should_retry": True, "reason": "analysis failed, default retry"}
