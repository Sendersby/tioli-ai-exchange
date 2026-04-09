"""ARCH-FF-002: Cross-agent anomaly correlation engine."""
import os, logging, json
log = logging.getLogger("arch.anomaly_correlation")

async def post_anomaly(db, source_agent, anomaly_type, severity, details, entity_ref=None):
    """Post an anomaly event."""
    if os.environ.get("ARCH_FF_ANOMALY_CORRELATION_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    from sqlalchemy import text
    import uuid
    await db.execute(text(
        "INSERT INTO anomaly_events (source_agent, anomaly_type, entity_ref, severity, details) "
        "VALUES (:src, :type, :ref, :sev, :det)"
    ), {"src": source_agent, "type": anomaly_type, "ref": entity_ref,
        "sev": severity, "det": json.dumps(details)})
    await db.commit()
    return {"status": "posted", "source": source_agent, "type": anomaly_type}

async def check_correlations(db):
    """Check for correlated anomalies in the last 30 minutes."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT event_id, source_agent, anomaly_type, entity_ref, severity "
        "FROM anomaly_events WHERE created_at > now() - interval '30 minutes' AND correlated = false"
    ))
    events = result.fetchall()
    if len(events) < 2:
        return {"correlations": 0}

    sources = set(e.source_agent for e in events)

    # Check entity-based correlation: same entity flagged by 2+ agents
    entity_refs = {}
    for e in events:
        if e.entity_ref:
            entity_refs.setdefault(e.entity_ref, set()).add(e.source_agent)
    entity_correlated = {ref: agents for ref, agents in entity_refs.items() if len(agents) >= 2}

    if entity_correlated:
        import uuid
        cid = str(uuid.uuid4())
        ref = list(entity_correlated.keys())[0]
        related = [e for e in events if e.entity_ref == ref]
        eids = [str(e.event_id) for e in related]
        await db.execute(text(
            "INSERT INTO anomaly_correlations (correlation_id, event_ids, sources, pattern, combined_severity, narrative) "
            "VALUES (:cid, :eids, :srcs, 'ENTITY_CORRELATION', 'high', :narr)"
        ), {"cid": cid, "eids": eids, "srcs": list(entity_correlated[ref]),
            "narr": f"Entity {ref} flagged by {len(entity_correlated[ref])} agents: {', '.join(entity_correlated[ref])}"})
        for e in related:
            await db.execute(text("UPDATE anomaly_events SET correlated=true, correlation_id=:cid WHERE event_id=:eid"),
                           {"cid": cid, "eid": e.event_id})
        await db.commit()
        return {"correlations": 1, "pattern": "ENTITY_CORRELATION", "entity": ref, "events": len(related), "agents": list(entity_correlated[ref])}

    # CASCADING_FAILURE: critical + high within 10 minutes
    critical_events = [e for e in events if e.severity == 'critical']
    high_events = [e for e in events if e.severity == 'high']
    if critical_events and high_events:
        import uuid
        cid = str(uuid.uuid4())
        cascade = critical_events + high_events
        eids = [str(e.event_id) for e in cascade]
        await db.execute(text(
            "INSERT INTO anomaly_correlations (correlation_id, event_ids, sources, pattern, combined_severity, narrative) "
            "VALUES (:cid, :eids, :srcs, 'CASCADING_FAILURE', 'critical', :narr)"
        ), {"cid": cid, "eids": eids, "srcs": list(set(e.source_agent for e in cascade)),
            "narr": f"Cascading failure: {len(critical_events)} critical + {len(high_events)} high events in 30 min"})
        for e in cascade:
            await db.execute(text("UPDATE anomaly_events SET correlated=true, correlation_id=:cid WHERE event_id=:eid"),
                           {"cid": cid, "eid": e.event_id})
        await db.commit()
        return {"correlations": 1, "pattern": "CASCADING_FAILURE", "events": len(cascade)}

    if len(sources) >= 3:
        # COORDINATED_ANOMALY
        import uuid
        cid = str(uuid.uuid4())
        eids = [str(e.event_id) for e in events]
        await db.execute(text(
            "INSERT INTO anomaly_correlations (correlation_id, event_ids, sources, pattern, combined_severity, narrative) "
            "VALUES (:cid, :eids, :srcs, 'COORDINATED_ANOMALY', 'critical', :narr)"
        ), {"cid": cid, "eids": eids, "srcs": list(sources),
            "narr": f"Coordinated anomaly: {len(events)} events from {len(sources)} agents in 30 min"})
        for e in events:
            await db.execute(text("UPDATE anomaly_events SET correlated=true, correlation_id=:cid WHERE event_id=:eid"),
                           {"cid": cid, "eid": e.event_id})
        await db.commit()
        return {"correlations": 1, "pattern": "COORDINATED_ANOMALY", "events": len(events)}
    return {"correlations": 0, "events_checked": len(events)}
