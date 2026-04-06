"""Structured memory tools for Arch Agents — retain, recall, reflect.

Inspired by Hindsight MCP memory server. Uses existing pgvector infrastructure.
Three operations:
  - retain: Store a memory with metadata and importance scoring
  - recall: Hybrid retrieval (semantic + keyword + RRF) with context
  - reflect: Synthesize multiple memories into a coherent summary
"""
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.memory_tools")


MEMORY_TOOLS = [
    {
        "name": "retain",
        "description": "Store important information in long-term memory. Use for: decisions made, founder directives, lessons learned, platform state changes, key metrics. Include why this matters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "What to remember — be specific and include context"},
                "importance": {"type": "string", "enum": ["critical", "high", "medium", "low"], "description": "How important is this memory"},
                "category": {"type": "string", "description": "Category: decision, directive, lesson, metric, event, relationship"},
            },
            "required": ["content", "importance"],
        },
    },
    {
        "name": "recall",
        "description": "Search long-term memory for relevant information. Searches both by meaning (semantic) and by exact terms (keyword). Use before making decisions to check what you already know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What are you trying to remember? Be specific."},
                "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "reflect",
        "description": "Synthesize your memories on a topic into a coherent understanding. Use when you need to form a position, write a report, or advise the founder on a complex topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What topic to reflect on"},
                "purpose": {"type": "string", "description": "Why are you reflecting? What decision does this inform?"},
            },
            "required": ["topic"],
        },
    },
]


async def execute_retain(agent, args: dict) -> dict:
    """Store a structured memory."""
    content = args.get("content", "")
    importance = args.get("importance", "medium")
    category = args.get("category", "general")

    importance_scores = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.3}

    await agent.remember(
        content,
        metadata={"category": category, "importance": importance, "retained_at": datetime.now(timezone.utc).isoformat()},
        source_type="retain",
        importance=importance_scores.get(importance, 0.5),
    )
    return {"stored": True, "importance": importance, "category": category}


async def execute_recall(agent, args: dict) -> dict:
    """Search memory with hybrid retrieval."""
    query = args.get("query", "")
    limit = args.get("limit", 5)

    memories = await agent.recall(query)
    results = memories[:limit] if memories else []

    return {
        "query": query,
        "results_found": len(results),
        "memories": [
            {
                "content": m.get("content", ""),
                "source": m.get("source_type", ""),
                "relevance": m.get("similarity", 0),
            }
            for m in results
        ],
    }


async def execute_reflect(agent, args: dict) -> dict:
    """Synthesize memories on a topic into a coherent understanding."""
    topic = args.get("topic", "")
    purpose = args.get("purpose", "general reflection")

    # Recall relevant memories
    memories = await agent.recall(topic)

    if not memories:
        return {"reflection": f"I have no memories related to '{topic}'.", "memories_used": 0}

    # Build a synthesis from the memories
    memory_texts = [m.get("content", "") for m in memories[:10]]
    synthesis = f"Reflection on '{topic}' (based on {len(memory_texts)} memories):\n\n"
    synthesis += "Key points from memory:\n"
    for i, mt in enumerate(memory_texts, 1):
        synthesis += f"  {i}. {mt[:200]}\n"

    return {
        "topic": topic,
        "purpose": purpose,
        "memories_used": len(memory_texts),
        "reflection": synthesis,
    }


# Handler map for tool dispatch
MEMORY_TOOL_HANDLERS = {
    "retain": execute_retain,
    "recall": execute_recall,
    "reflect": execute_reflect,
}
