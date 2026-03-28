"""Workflow Map Service — graph assembly, caching, and feature flag sync."""

import time
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from app.workflow_map.models import WorkflowMapNode, WorkflowMapEdge, WorkflowMapStatusHistory
from app.config import Settings

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
