"""Patch main.py lifespan to activate autonomous event loops + scheduler."""

with open("app/main.py") as f:
    content = f.read()

old_block = '''    # ── Arch Agent Initiative — Startup ──────────────────────
    # Additive only. Conditional on ARCH_AGENTS_ENABLED.
    import os as _arch_os
    if _arch_os.getenv("ARCH_AGENTS_ENABLED", "false").lower() == "true":
        try:
            import redis.asyncio as _arch_redis
            from app.arch.agents import initialise_arch_agents
            _arch_redis_client = _arch_redis.from_url(
                _arch_os.getenv("REDIS_URL", "redis://localhost:6379/0")
            )
            async with async_session() as _arch_db:
                _arch_agents = await initialise_arch_agents(
                    _arch_db, _arch_redis_client
                )
            print(f"  Arch Agents: {len(_arch_agents)} activated")
        except Exception as _arch_e:
            print(f"  Arch Agents: startup failed — {_arch_e}")
    yield
    stop_scheduler()'''

new_block = '''    # ── Arch Agent Initiative — Startup ──────────────────────
    # Additive only. Conditional on ARCH_AGENTS_ENABLED.
    import os as _arch_os
    import asyncio as _arch_asyncio
    _arch_event_loops = []
    _arch_scheduler = None
    if _arch_os.getenv("ARCH_AGENTS_ENABLED", "false").lower() == "true":
        try:
            import redis.asyncio as _arch_redis
            from app.arch.agents import initialise_arch_agents
            _arch_redis_client = _arch_redis.from_url(
                _arch_os.getenv("REDIS_URL", "redis://localhost:6379/0")
            )
            async with async_session() as _arch_db:
                _arch_agents = await initialise_arch_agents(
                    _arch_db, _arch_redis_client
                )
            print(f"  Arch Agents: {len(_arch_agents)} activated")

            # ── Register APScheduler jobs (heartbeats, reserves, board sessions, etc.)
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                from app.arch.scheduler import register_arch_jobs
                _arch_scheduler = AsyncIOScheduler(timezone="Africa/Johannesburg")
                register_arch_jobs(_arch_scheduler, _arch_agents, db_factory=async_session)
                _arch_scheduler.start()
                print(f"  Arch Scheduler: {len(_arch_scheduler.get_jobs())} jobs registered")
            except Exception as _sched_e:
                print(f"  Arch Scheduler: failed — {_sched_e}")

            # ── Start autonomous event loops for each agent
            try:
                from app.arch.event_loop import ArchEventLoop
                for _agent_name, _agent_obj in _arch_agents.items():
                    _loop = ArchEventLoop(
                        agent=_agent_obj,
                        agent_id=_agent_name,
                        db_factory=async_session,
                        redis=_arch_redis_client,
                    )
                    _task = _arch_asyncio.create_task(
                        _loop.start(),
                        name=f"arch_event_loop_{_agent_name}",
                    )
                    _arch_event_loops.append((_agent_name, _loop, _task))
                print(f"  Arch Event Loops: {len(_arch_event_loops)} agents autonomous")
            except Exception as _loop_e:
                print(f"  Arch Event Loops: failed — {_loop_e}")

            # ── Start Redis urgent message listener
            try:
                from app.arch.messaging import start_urgent_listener
                _arch_asyncio.create_task(
                    start_urgent_listener(_arch_redis_client, _arch_agents),
                    name="arch_urgent_listener",
                )
                print(f"  Arch Messaging: urgent listener active")
            except Exception as _msg_e:
                print(f"  Arch Messaging: failed — {_msg_e}")

        except Exception as _arch_e:
            print(f"  Arch Agents: startup failed — {_arch_e}")
    yield
    # Shutdown
    for _name, _loop, _task in _arch_event_loops:
        _loop.stop()
        _task.cancel()
    if _arch_scheduler:
        _arch_scheduler.shutdown(wait=False)
    stop_scheduler()'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open("app/main.py", "w") as f:
        f.write(content)
    print("LIFESPAN PATCHED — scheduler + event loops + messaging activated")
else:
    print("ERROR: Could not find the old block to replace")
    # Debug
    if "Arch Agent Initiative" in content:
        idx = content.index("Arch Agent Initiative")
        print(f"Found at index {idx}")
        print(content[idx:idx+200])
