"""Multi-step task planning — agents decompose goals into executable steps."""
import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.planner")


class TaskPlan:
    """A multi-step plan that an agent executes sequentially."""

    def __init__(self, goal: str, agent_name: str, steps: list):
        self.id = str(uuid.uuid4())
        self.goal = goal
        self.agent_name = agent_name
        self.steps = steps  # List of {"description": str, "tool": str, "params": dict}
        self.current_step = 0
        self.status = "pending"  # pending, in_progress, completed, failed
        self.results = []
        self.created_at = datetime.now(timezone.utc)
        self.errors = []

    def next_step(self):
        """Get the next step to execute."""
        if self.current_step >= len(self.steps):
            self.status = "completed"
            return None
        return self.steps[self.current_step]

    def record_result(self, result, success=True):
        """Record the result of executing a step."""
        self.results.append({
            "step": self.current_step,
            "description": self.steps[self.current_step]["description"],
            "result": str(result)[:500],
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if success:
            self.current_step += 1
            if self.current_step >= len(self.steps):
                self.status = "completed"
            else:
                self.status = "in_progress"
        else:
            self.errors.append({"step": self.current_step, "error": str(result)[:500]})

    def record_failure(self, error, can_retry=True):
        """Record a step failure."""
        self.errors.append({"step": self.current_step, "error": str(error)[:500], "retryable": can_retry})
        if not can_retry or len([e for e in self.errors if e["step"] == self.current_step]) >= 3:
            self.status = "failed"

    def summary(self):
        """Get plan execution summary."""
        return {
            "plan_id": self.id,
            "goal": self.goal,
            "agent": self.agent_name,
            "total_steps": len(self.steps),
            "completed_steps": self.current_step,
            "status": self.status,
            "errors": len(self.errors),
            "results": self.results,
        }


async def create_plan_from_goal(agent_client, goal: str, agent_name: str) -> TaskPlan:
    """Use Claude to decompose a goal into executable steps."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=[{"type": "text", "text": f"You are {agent_name}, an AI executive agent. Decompose the given goal into 3-7 concrete, executable steps. Each step should be a single action. Return as JSON array: [{{\"description\": \"step text\", \"tool\": \"tool_name\", \"params\": {{}}}}]"}],
            messages=[{"role": "user", "content": f"Decompose this goal into steps: {goal}"}],
        )
        import json
        text = next((b.text for b in response.content if b.type == "text"), "[]")
        # Extract JSON from response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            steps = json.loads(text[start:end])
        else:
            steps = [{"description": goal, "tool": "general", "params": {}}]

        plan = TaskPlan(goal=goal, agent_name=agent_name, steps=steps)
        plan.status = "in_progress"
        log.info(f"[planner] Created plan {plan.id}: {len(steps)} steps for '{goal[:50]}'")
        return plan
    except Exception as e:
        log.warning(f"[planner] Failed to create plan: {e}")
        return TaskPlan(goal=goal, agent_name=agent_name,
                       steps=[{"description": goal, "tool": "general", "params": {}}])


async def save_plan_to_db(db, plan: TaskPlan):
    """Persist plan state to database."""
    from sqlalchemy import text
    import json
    try:
        await db.execute(text(
            "INSERT INTO arch_task_queue (id, agent_name, task_type, payload, status, created_at) "
            "VALUES (:id, :agent, 'plan', :payload, :status, now()) "
            "ON CONFLICT (id) DO UPDATE SET payload = :payload, status = :status"
        ), {
            "id": plan.id, "agent": plan.agent_name,
            "payload": json.dumps(plan.summary()), "status": plan.status,
        })
        await db.commit()
    except Exception as e:
        log.warning(f"[planner] DB save failed: {e}")


async def execute_plan(plan, agent_client, db=None):
    """Execute a plan step by step with retry on failure."""
    import logging
    log = logging.getLogger("arch.planner")

    while plan.status == "in_progress":
        step = plan.next_step()
        if step is None:
            break

        log.info(f"[planner] Executing step {plan.current_step + 1}/{len(plan.steps)}: {step['description'][:60]}")

        try:
            # Use Claude to execute/simulate the step
            response = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=[{"type": "text", "text": f"You are executing step {plan.current_step + 1} of a plan. Perform the action and report the result concisely."}],
                messages=[{"role": "user", "content": f"Execute this step: {step['description']}\n\nContext: Goal is '{plan.goal}'. Previous results: {[r['result'][:100] for r in plan.results[-3:]]}"}],
            )
            result = next((b.text for b in response.content if b.type == "text"), "No result")
            plan.record_result(result, success=True)
            log.info(f"[planner] Step {plan.current_step}/{len(plan.steps)} completed")

        except Exception as e:
            plan.record_failure(str(e), can_retry=True)
            log.warning(f"[planner] Step failed: {e}")

            # Retry logic
            if plan.status != "failed":
                log.info(f"[planner] Retrying step {plan.current_step + 1}...")
                continue
            else:
                log.error(f"[planner] Plan failed after retries")
                break

    # Save final state
    if db:
        await save_plan_to_db(db, plan)

    return plan.summary()
