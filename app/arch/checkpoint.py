"""H-003: Checkpoint & Rollback (Hermes-inspired).
Snapshot files before modification. Rollback via API.
Feature flag: ARCH_H_CHECKPOINT_ENABLED"""
import os
import logging
import uuid

log = logging.getLogger("arch.checkpoint")


async def create_checkpoint(db, agent_id: str, file_path: str,
                            content_before: str, description: str = None) -> str:
    """Create a checkpoint before modifying a file. Returns checkpoint_id."""
    if os.environ.get("ARCH_H_CHECKPOINT_ENABLED", "false").lower() != "true":
        return None

    from sqlalchemy import text
    cid = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO arch_checkpoints (checkpoint_id, agent_id, file_path, content_before, description) "
        "VALUES (cast(:cid as uuid), :aid, :path, :content, :desc)"
    ), {"cid": cid, "aid": agent_id, "path": file_path,
        "content": content_before[:100000], "desc": description})
    await db.commit()
    log.info(f"[checkpoint] Created {cid[:8]} for {file_path} by {agent_id}")
    return cid


async def record_after(db, checkpoint_id: str, content_after: str):
    """Record the file content after modification."""
    if not checkpoint_id:
        return
    from sqlalchemy import text
    await db.execute(text(
        "UPDATE arch_checkpoints SET content_after = :content WHERE checkpoint_id = cast(:cid as uuid)"
    ), {"content": content_after[:100000], "cid": checkpoint_id})
    await db.commit()


async def rollback_checkpoint(db, checkpoint_id: str) -> dict:
    """Rollback a file to its pre-checkpoint state."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT file_path, content_before, rolled_back FROM arch_checkpoints "
        "WHERE checkpoint_id = cast(:cid as uuid)"
    ), {"cid": checkpoint_id})
    row = r.fetchone()
    if not row:
        return {"error": "Checkpoint not found"}
    if row.rolled_back:
        return {"error": "Already rolled back"}

    # Write the original content back
    try:
        with open(row.file_path, "w") as f:
            f.write(row.content_before)
        await db.execute(text(
            "UPDATE arch_checkpoints SET rolled_back = true WHERE checkpoint_id = cast(:cid as uuid)"
        ), {"cid": checkpoint_id})
        await db.commit()
        log.info(f"[checkpoint] ROLLED BACK {checkpoint_id[:8]} -> {row.file_path}")
        return {"checkpoint_id": checkpoint_id, "file_path": row.file_path, "status": "rolled_back"}
    except Exception as e:
        return {"error": str(e), "file_path": row.file_path}


async def list_checkpoints(db, agent_id: str = None, limit: int = 20) -> list:
    """List recent checkpoints."""
    from sqlalchemy import text
    query = "SELECT checkpoint_id, agent_id, file_path, description, rolled_back, created_at FROM arch_checkpoints"
    params = {"limit": limit}
    if agent_id:
        query += " WHERE agent_id = :aid"
        params["aid"] = agent_id
    query += " ORDER BY created_at DESC LIMIT :limit"
    r = await db.execute(text(query), params)
    return [{"checkpoint_id": str(row.checkpoint_id), "agent_id": row.agent_id,
             "file_path": row.file_path, "description": row.description,
             "rolled_back": row.rolled_back,
             "created_at": str(row.created_at)} for row in r.fetchall()]
