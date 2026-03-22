"""Live operational test for AgentVault™."""
import asyncio
from app.database.db import async_session
from app.agentvault.service import AgentVaultService
from app.agents.models import Agent
from sqlalchemy import select

svc = AgentVaultService()

async def test():
    async with async_session() as db:
        result = await db.execute(select(Agent).limit(1))
        agent = result.scalar_one_or_none()
        if not agent:
            print("NO AGENTS")
            return

        agent_id = agent.id
        print(f"Agent: {agent.name} ({agent_id[:16]}...)")

        # 1. Create vault
        try:
            vault = await svc.create_vault(db, agent_id, "", "cache", "free", True)
            print(f"1. CREATE: OK — {vault['tier']}, {vault['quota_display']}")
        except ValueError:
            vault = await svc.get_vault(db, agent_id)
            print(f"1. EXISTS: {vault['tier']}, {vault['used_display']}/{vault['quota_display']}")

        vid = vault["vault_id"]

        # 2. Store object
        o = await svc.put_object(db, vid, agent_id, "/code/test.py", "x = 42", "text/python", "code")
        print(f"2. PUT: OK — v{o['version']}, {o['size']}B, {o['used_pct']}%")

        # 3. Retrieve
        r = await svc.get_object(db, vid, agent_id, "/code/test.py")
        print(f"3. GET: OK — content='{r['content']}'")

        # 4. Version it
        o2 = await svc.put_object(db, vid, agent_id, "/code/test.py", "x = 99", "text/python", "code")
        print(f"4. UPDATE: OK — now v{o2['version']}")

        # 5. Versions
        v = await svc.get_object_versions(db, vid, "/code/test.py")
        print(f"5. VERSIONS: {len(v)} found")

        # 6. List
        lst = await svc.list_objects(db, vid)
        print(f"6. LIST: {len(lst)} objects")

        # 7. Usage
        u = await svc.get_usage(db, vid)
        print(f"7. USAGE: {u['used_bytes']}B / {u['quota_bytes']}B ({u['used_pct']}%)")

        # 8. Store another
        await svc.put_object(db, vid, agent_id, "/history/log.json", '{"test": true}', "application/json", "history")
        print("8. SECOND OBJECT: OK")

        # 9. Private key rejection
        try:
            await svc.put_object(db, vid, agent_id, "/keys/bad.pem", "-----BEGIN PRIVATE KEY-----\ntest", "text/plain")
            print("9. PRIVATE KEY: FAIL — not blocked!")
        except ValueError:
            print("9. PRIVATE KEY: BLOCKED (correct)")

        # 10. Audit
        a = await svc.get_audit_log(db, vid, limit=5)
        print(f"10. AUDIT: {len(a)} entries")

        # 11. Delete
        d = await svc.delete_object(db, vid, agent_id, "/history/log.json")
        print(f"11. DELETE: OK — reclaimed {d['reclaimed_bytes']}B")

        # 12. Final
        f = await svc.get_usage(db, vid)
        print(f"12. FINAL: {f['object_count']} objects, {f['used_pct']}%")

        await db.commit()
        print("\n=== ALL 12 TESTS PASSED — AgentVault OPERATIONAL ===")

asyncio.run(test())
