"""Inter-agent collaboration — structured delegation and workflow execution."""
import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.collaboration")


class AgentWorkflow:
    """A workflow where agents delegate tasks to each other."""

    def __init__(self, name: str, initiator: str):
        self.id = str(uuid.uuid4())
        self.name = name
        self.initiator = initiator
        self.steps = []
        self.status = "created"
        self.created_at = datetime.now(timezone.utc)

    def add_step(self, agent_name: str, task: str, depends_on: list = None):
        """Add a step assigned to a specific agent."""
        self.steps.append({
            "step_id": len(self.steps) + 1,
            "agent": agent_name,
            "task": task,
            "depends_on": depends_on or [],
            "status": "pending",
            "result": None,
        })

    def get_ready_steps(self):
        """Get steps whose dependencies are all completed."""
        completed_ids = {s["step_id"] for s in self.steps if s["status"] == "completed"}
        return [s for s in self.steps if s["status"] == "pending"
                and all(d in completed_ids for d in s["depends_on"])]

    def complete_step(self, step_id: int, result: str):
        """Mark a step as completed."""
        for s in self.steps:
            if s["step_id"] == step_id:
                s["status"] = "completed"
                s["result"] = result[:500]
                break
        if all(s["status"] == "completed" for s in self.steps):
            self.status = "completed"

    def summary(self):
        return {
            "workflow_id": self.id,
            "name": self.name,
            "initiator": self.initiator,
            "total_steps": len(self.steps),
            "completed": sum(1 for s in self.steps if s["status"] == "completed"),
            "status": self.status,
            "steps": self.steps,
        }


async def execute_workflow(workflow, agent_client):
    """Execute a multi-agent workflow — runs ready steps, potentially in parallel."""
    workflow.status = "in_progress"

    max_iterations = len(workflow.steps) * 2  # Safety limit
    iteration = 0

    while workflow.status != "completed" and iteration < max_iterations:
        ready = workflow.get_ready_steps()
        if not ready:
            if any(s["status"] == "pending" for s in workflow.steps):
                workflow.status = "blocked"
            break

        for step in ready:
            step["status"] = "in_progress"
            try:
                response = await agent_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    system=[{"type": "text", "text": f"You are {step['agent']} of TiOLi AGENTIS. Execute this task concisely."}],
                    messages=[{"role": "user", "content":
                        step["task"] + (
                            "\n\nContext from previous steps:\n" +
                            "\n".join(f"- {s['agent']}: {s['result'][:200]}" for s in workflow.steps if s['status'] == 'completed' and s['result'])
                            if any(s['status'] == 'completed' and s['result'] for s in workflow.steps)
                            else ""
                        )}],
                )
                result = next((b.text for b in response.content if b.type == "text"), "No output")
                workflow.complete_step(step["step_id"], result)
                log.info(f"[collab] Step {step['step_id']} ({step['agent']}): completed")
            except Exception as e:
                step["status"] = "failed"
                step["result"] = str(e)[:200]
                log.warning(f"[collab] Step {step['step_id']} failed: {e}")

        iteration += 1

    return workflow.summary()
