"""Workflow Map Service — graph assembly, caching, feature flag sync, and enrichment."""

import time
import httpx
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, or_, text
from app.workflow_map.models import WorkflowMapNode, WorkflowMapEdge, WorkflowMapStatusHistory
from app.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()

# In-memory cache: {"graph": data, "timestamp": float}
_cache: dict = {}
CACHE_TTL = 30  # seconds


def _invalidate_cache():
    _cache.clear()


def _node_to_dict(n: WorkflowMapNode) -> dict:
    return {
        "id": n.node_id,
        "label": n.label,
        "category": n.category,
        "status": n.status,
        "node_type": n.node_type,
        "description": n.description,
        "url_path": n.url_path,
        "api_endpoint": n.api_endpoint,
        "feature_flag": n.feature_flag,
        "linked_endpoints": n.linked_endpoints or [],
        "metadata": n.metadata_ or {},
    }


def _edge_to_dict(e: WorkflowMapEdge) -> dict:
    return {
        "id": e.edge_id,
        "source": e.source_node_id,
        "target": e.target_node_id,
        "flow_type": e.flow_type,
        "direction": e.direction,
        "label": e.label,
        "is_critical_path": e.is_critical_path,
        "condition": e.condition,
    }


def _sync_feature_flag_status(node_dict: dict) -> dict:
    """Cross-reference node's feature_flag against platform settings.
    If the flag is False and node is ACTIVE, override to INACTIVE."""
    flag = node_dict.get("feature_flag")
    if flag and node_dict["status"] == "ACTIVE":
        flag_value = getattr(settings, flag, None)
        if flag_value is False:
            node_dict["status"] = "INACTIVE"
    return node_dict


class WorkflowMapService:

    async def get_graph(self, db) -> dict:
        """Return complete node/edge graph with meta counts. Cached for 30s."""
        cached = _cache.get("graph")
        if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
            return cached["data"]

        nodes_result = await db.execute(select(WorkflowMapNode))
        nodes = [_sync_feature_flag_status(_node_to_dict(n)) for n in nodes_result.scalars().all()]

        edges_result = await db.execute(select(WorkflowMapEdge))
        edges = [_edge_to_dict(e) for e in edges_result.scalars().all()]

        # Count by status
        status_counts = {}
        for n in nodes:
            s = n["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        data = {
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "active_count": status_counts.get("ACTIVE", 0),
                "restricted_count": status_counts.get("RESTRICTED", 0),
                "inactive_count": status_counts.get("INACTIVE", 0),
                "planned_count": status_counts.get("PLANNED", 0),
                "deprecated_count": status_counts.get("DEPRECATED", 0),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        }

        _cache["graph"] = {"data": data, "timestamp": time.time()}
        return data

    async def get_node_detail(self, db, node_id: str) -> dict | None:
        """Return full detail for a single node with connections and history."""
        result = await db.execute(
            select(WorkflowMapNode).where(WorkflowMapNode.node_id == node_id)
        )
        node = result.scalar_one_or_none()
        if not node:
            return None

        node_dict = _sync_feature_flag_status(_node_to_dict(node))

        # Connected edges
        inbound = await db.execute(
            select(WorkflowMapEdge).where(WorkflowMapEdge.target_node_id == node_id)
        )
        outbound = await db.execute(
            select(WorkflowMapEdge).where(WorkflowMapEdge.source_node_id == node_id)
        )
        inbound_edges = [_edge_to_dict(e) for e in inbound.scalars().all()]
        outbound_edges = [_edge_to_dict(e) for e in outbound.scalars().all()]

        connected_ids = set()
        for e in inbound_edges:
            connected_ids.add(e["source"])
        for e in outbound_edges:
            connected_ids.add(e["target"])

        # Status history (last 10)
        history_result = await db.execute(
            select(WorkflowMapStatusHistory)
            .where(WorkflowMapStatusHistory.node_id == node_id)
            .order_by(WorkflowMapStatusHistory.changed_at.desc())
            .limit(10)
        )
        history = [
            {
                "status": h.new_status,
                "previous_status": h.previous_status,
                "reason": h.reason,
                "changed_by": h.changed_by,
                "changed_at": h.changed_at.isoformat() if h.changed_at else None,
            }
            for h in history_result.scalars().all()
        ]

        return {
            "node": node_dict,
            "connected_nodes": list(connected_ids),
            "inbound_edges": inbound_edges,
            "outbound_edges": outbound_edges,
            "status_history": history,
        }

    async def get_status_summary(self, db) -> dict:
        """Lightweight status/category counts for the stats bar."""
        nodes_result = await db.execute(select(WorkflowMapNode))
        nodes = nodes_result.scalars().all()

        by_status = {}
        by_category = {}
        for n in nodes:
            s = n.status
            c = n.category
            by_status[s] = by_status.get(s, 0) + 1
            by_category[c] = by_category.get(c, 0) + 1

        # Last status change
        last_change = await db.execute(
            select(WorkflowMapStatusHistory.changed_at)
            .order_by(WorkflowMapStatusHistory.changed_at.desc())
            .limit(1)
        )
        last_ts = last_change.scalar_one_or_none()

        return {
            "by_status": {
                "ACTIVE": by_status.get("ACTIVE", 0),
                "RESTRICTED": by_status.get("RESTRICTED", 0),
                "INACTIVE": by_status.get("INACTIVE", 0),
                "PLANNED": by_status.get("PLANNED", 0),
                "DEPRECATED": by_status.get("DEPRECATED", 0),
            },
            "by_category": {
                "REGISTRATION": by_category.get("REGISTRATION", 0),
                "PAYMENT": by_category.get("PAYMENT", 0),
                "COMPLIANCE": by_category.get("COMPLIANCE", 0),
                "AGENT_SERVICE": by_category.get("AGENT_SERVICE", 0),
                "NAVIGATION": by_category.get("NAVIGATION", 0),
                "API": by_category.get("API", 0),
                "MCP": by_category.get("MCP", 0),
            },
            "last_status_change": last_ts.isoformat() if last_ts else None,
        }

    async def update_node_status(self, db, node_id: str, new_status: str, reason: str = None) -> dict | None:
        """Update a node's status and record in history."""
        result = await db.execute(
            select(WorkflowMapNode).where(WorkflowMapNode.node_id == node_id)
        )
        node = result.scalar_one_or_none()
        if not node:
            return None

        old_status = node.status

        # Write history
        history = WorkflowMapStatusHistory(
            node_id=node_id,
            previous_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by="owner",
        )
        db.add(history)

        # Update node
        node.status = new_status
        node.updated_at = datetime.now(timezone.utc)
        await db.commit()

        _invalidate_cache()
        return _sync_feature_flag_status(_node_to_dict(node))

    async def get_enrichment_data(self, db) -> dict:
        """Gather all enrichment data for all nodes — health, traffic, revenue,
        build phases, dependency warnings, last activity, and agent counts."""

        result = await db.execute(select(WorkflowMapNode))
        nodes = result.scalars().all()
        edges_result = await db.execute(select(WorkflowMapEdge))
        edges = edges_result.scalars().all()

        enrichment = {}

        # --- 1. Health check: ping endpoints that have url_path or api_endpoint ---
        health_endpoints = []
        for n in nodes:
            if n.url_path and n.status == 'ACTIVE':
                health_endpoints.append((n.node_id, n.url_path))
            elif n.api_endpoint and n.status == 'ACTIVE':
                # Extract just the path from "GET /api/..." or "POST /api/..."
                parts = (n.api_endpoint or '').split(' ')
                path = parts[-1] if parts else None
                if path and path.startswith('/'):
                    health_endpoints.append((n.node_id, path))

        health_results = {}
        try:
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8000', timeout=3) as client:
                for node_id, path in health_endpoints[:30]:  # Cap at 30 to avoid slowness
                    try:
                        r = await client.get(path)
                        if r.status_code < 500:
                            health_results[node_id] = 'green'
                        else:
                            health_results[node_id] = 'red'
                    except Exception as e:
                        health_results[node_id] = 'red'
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # --- 2. Traffic heatmap: count requests from nginx access log ---
        traffic_counts = {}
        try:
            import os
            log_path = '/var/log/nginx/access.log'
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    lines = f.readlines()[-5000:]  # Last 5000 lines
                for line in lines:
                    for n in nodes:
                        if n.url_path and n.url_path != '/' and n.url_path in line:
                            traffic_counts[n.node_id] = traffic_counts.get(n.node_id, 0) + 1
                        elif n.api_endpoint:
                            parts = (n.api_endpoint or '').split(' ')
                            path = parts[-1] if parts else ''
                            if path and path in line:
                                traffic_counts[n.node_id] = traffic_counts.get(n.node_id, 0) + 1
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # Normalise traffic to 0-1 scale
        max_traffic = max(traffic_counts.values()) if traffic_counts else 1
        traffic_heat = {}
        for nid, count in traffic_counts.items():
            traffic_heat[nid] = round(count / max(max_traffic, 1), 3)

        # --- 3. Revenue flow: get transaction volume through payment nodes ---
        revenue_data = {}
        try:
            from app.agents.models import Wallet
            total_agentis = (await db.execute(
                select(func.sum(Wallet.balance)).where(Wallet.currency == 'AGENTIS')
            )).scalar() or 0
            # Assign revenue to payment nodes proportionally
            payment_nodes = [n for n in nodes if n.category == 'PAYMENT' and n.status == 'ACTIVE']
            if payment_nodes:
                share = round(total_agentis / len(payment_nodes), 1)
                for n in payment_nodes:
                    revenue_data[n.node_id] = share
            revenue_data['_total'] = round(total_agentis, 1)
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # --- 4. Build phases: extract from node metadata ---
        build_phases = {}
        for n in nodes:
            meta = n.metadata_ or {}
            phase = meta.get('build_phase')
            if phase:
                build_phases[n.node_id] = phase

        # --- 5. Dependency warnings: PLANNED nodes depending on INACTIVE nodes ---
        dependency_warnings = []
        node_status_map = {n.node_id: n.status for n in nodes}
        for e in edges:
            src_status = node_status_map.get(e.source_node_id, '')
            tgt_status = node_status_map.get(e.target_node_id, '')
            # If target is PLANNED but source is INACTIVE — blocked dependency
            if tgt_status == 'PLANNED' and src_status == 'INACTIVE':
                dependency_warnings.append({
                    'blocked_node': e.target_node_id,
                    'blocking_node': e.source_node_id,
                    'edge_id': e.edge_id,
                })
            # If source is PLANNED but target is INACTIVE — also a concern
            if src_status == 'PLANNED' and tgt_status == 'INACTIVE':
                dependency_warnings.append({
                    'blocked_node': e.source_node_id,
                    'blocking_node': e.target_node_id,
                    'edge_id': e.edge_id,
                })

        # --- 6. Last activity: from platform_events or blockchain ---
        last_activity = {}
        try:
            from app.agent_profile.models import PlatformEvent
            recent = await db.execute(
                select(PlatformEvent.related_entity_type, func.max(PlatformEvent.created_at))
                .group_by(PlatformEvent.related_entity_type)
            )
            for entity_type, ts in recent.all():
                if entity_type and ts:
                    # Map entity types to node IDs roughly
                    type_map = {
                        'engagement': 'node_svc_agentbroker_contract',
                        'agent': 'node_reg_agent_create',
                        'governance': 'node_dash_governance',
                        'wallet': 'node_pay_credits',
                        'profile': 'node_svc_agent_profile',
                    }
                    nid = type_map.get(entity_type)
                    if nid:
                        last_activity[nid] = ts.isoformat()
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # --- 7. Agent counts per service ---
        agent_counts = {}
        try:
            from app.agents.models import Agent
            total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            # Agent registration
            agent_counts['node_reg_agent_create'] = total_agents
            # Agents with profiles
            from app.agenthub.models import AgentHubProfile
            profiles = (await db.execute(select(func.count(AgentHubProfile.id)))).scalar() or 0
            agent_counts['node_svc_agent_profile'] = profiles
            # Agents with services
            from app.agentbroker.models import AgentServiceProfile
            services = (await db.execute(select(func.count(AgentServiceProfile.id)))).scalar() or 0
            agent_counts['node_svc_agentbroker_profile'] = services
            # MCP — all agents can use it
            agent_counts['node_mcp_server'] = total_agents
            agent_counts['node_mcp_tool_discovery'] = total_agents
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # Assemble
        for n in nodes:
            nid = n.node_id
            enrichment[nid] = {
                'health': health_results.get(nid, 'unknown'),
                'traffic_heat': traffic_heat.get(nid, 0),
                'traffic_count': traffic_counts.get(nid, 0),
                'revenue': revenue_data.get(nid, 0),
                'build_phase': build_phases.get(nid),
                'agent_count': agent_counts.get(nid, 0),
                'last_activity': last_activity.get(nid),
                'has_dependency_warning': any(
                    w['blocked_node'] == nid or w['blocking_node'] == nid
                    for w in dependency_warnings
                ),
            }

        return {
            'nodes': enrichment,
            'revenue_total': revenue_data.get('_total', 0),
            'dependency_warnings': dependency_warnings,
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }
