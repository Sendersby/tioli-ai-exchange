"""LangGraph StateGraph for Arch Agent orchestration.

All external triggers enter via The Sovereign, which routes to the
appropriate agent. Financial actions pass through a gate check first.
"""

from typing import List, Literal, Optional, TypedDict


class ArchAgentState(TypedDict):
    session_id: str
    originating_agent: str
    instruction: str
    instruction_type: Literal[
        "governance", "compliance", "justice", "finance",
        "security", "technology", "growth", "board", "emergency",
    ]
    context: dict
    memory_retrieved: List[dict]
    tool_results: List[dict]
    inter_agent_messages: List[dict]
    board_vote_required: bool
    board_vote_status: Optional[str]
    founder_approval_required: bool
    founder_approval_status: Optional[str]
    financial_gate_cleared: bool
    tier: Optional[int]
    escalation_chain: List[str]
    defer_to_owner: bool
    defer_reason: Optional[str]
    output: Optional[str]
    error: Optional[str]
    action_taken: Optional[str]


def route_instruction(state: ArchAgentState) -> str:
    """Route instruction to the appropriate agent based on type."""
    t = state["instruction_type"]
    routing = {
        "governance": "sovereign",
        "compliance": "auditor",
        "justice": "arbiter",
        "finance": "treasurer",
        "security": "sentinel",
        "technology": "architect",
        "growth": "ambassador",
        "board": "sovereign",
        "emergency": "sentinel",
    }
    return routing.get(t, "sovereign")


def financial_gate(state: ArchAgentState) -> str:
    """Financial actions must pass reserve/ceiling check first."""
    if state.get("financial_gate_cleared"):
        return route_instruction(state)
    return "financial_check"


def build_arch_graph(nodes: dict, checkpointer=None):
    """Assemble the LangGraph StateGraph for all Arch Agents.

    Args:
        nodes: dict mapping agent_name -> agent callable
        checkpointer: optional LangGraph checkpointer for persistence
    """
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(ArchAgentState)

    # Add all agent nodes
    for name, node in nodes.items():
        graph.add_node(name, node)

    # Add utility nodes
    if "treasurer" in nodes:
        graph.add_node("financial_check", nodes["treasurer"].financial_gate_check)
    if "sovereign" in nodes:
        graph.add_node("board_vote", nodes["sovereign"].conduct_board_vote)
        graph.add_node("founder_notify", nodes["sovereign"].notify_founder)

    # Entry: all flows start at sovereign for routing
    graph.add_edge(START, "sovereign")

    # Build conditional routing targets
    route_targets = {
        "financial_check": "financial_check",
        "sovereign": "sovereign",
    }
    for agent_name in ["auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"]:
        if agent_name in nodes:
            route_targets[agent_name] = agent_name

    # Conditional routing from sovereign
    graph.add_conditional_edges("sovereign", financial_gate, route_targets)

    # All agents can route to board vote or founder notify or END
    def post_agent_route(s):
        if s.get("board_vote_required"):
            return "board_vote"
        if s.get("founder_approval_required"):
            return "founder_notify"
        return END

    post_targets = {END: END}
    if "sovereign" in nodes:
        post_targets["board_vote"] = "board_vote"
        post_targets["founder_notify"] = "founder_notify"

    for agent in ["auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"]:
        if agent in nodes:
            graph.add_conditional_edges(agent, post_agent_route, post_targets)

    if "financial_check" in [n for n in graph.nodes]:
        graph.add_edge("financial_check", "sovereign")
    if "board_vote" in [n for n in graph.nodes]:
        graph.add_edge("board_vote", "founder_notify")
    if "founder_notify" in [n for n in graph.nodes]:
        graph.add_edge("founder_notify", END)

    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
