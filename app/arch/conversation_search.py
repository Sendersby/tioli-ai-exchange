"""H-010: Conversation History Full-Text Search (Hermes-inspired).
FTS across all agent conversation logs.
Feature flag: ARCH_H_CONVERSATION_SEARCH_ENABLED"""
import os
import logging

log = logging.getLogger("arch.conversation_search")


async def log_conversation(db, agent_id: str, role: str, content: str,
                           tokens: int = 0, session_id: str = None):
    """Log a conversation turn for future search."""
    if os.environ.get("ARCH_H_CONVERSATION_SEARCH_ENABLED", "false").lower() != "true":
        return
    from sqlalchemy import text
    await db.execute(text(
        "INSERT INTO arch_conversation_log (agent_id, role, content, tokens_used, session_id) "
        "VALUES (:aid, :role, :content, :tokens, :sid)"
    ), {"aid": agent_id, "role": role, "content": content[:10000],
        "tokens": tokens, "sid": session_id})
    await db.commit()


async def search_conversations(db, query: str, agent_id: str = None,
                                limit: int = 20) -> list[dict]:
    """Full-text search across conversation history."""
    from sqlalchemy import text

    sql = (
        "SELECT log_id, agent_id, role, content, tokens_used, created_at, "
        "ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)) as rank "
        "FROM arch_conversation_log "
        "WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :q)"
    )
    params = {"q": query, "limit": limit}

    if agent_id:
        sql += " AND agent_id = :aid"
        params["aid"] = agent_id

    sql += " ORDER BY rank DESC, created_at DESC LIMIT :limit"

    r = await db.execute(text(sql), params)
    return [{"log_id": str(row.log_id), "agent_id": row.agent_id,
             "role": row.role, "content": row.content[:300],
             "tokens": row.tokens_used, "rank": float(row.rank),
             "created_at": str(row.created_at)} for row in r.fetchall()]
