"""Workflow Map database models — nodes, edges, and status history."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Boolean, Text, JSON, ForeignKey, Index
from app.database.db import Base


class WorkflowMapNode(Base):
    """A node in the platform workflow map — represents a page, service, endpoint, or feature."""
    __tablename__ = "workflow_map_nodes"

    node_id = Column(String(100), primary_key=True)
    label = Column(String(200), nullable=False)
    category = Column(String(30), nullable=False)  # REGISTRATION, PAYMENT, COMPLIANCE, AGENT_SERVICE, NAVIGATION, API, MCP
    status = Column(String(20), nullable=False, default="PLANNED")  # ACTIVE, RESTRICTED, INACTIVE, PLANNED, DEPRECATED
    node_type = Column(String(20), nullable=False)  # PAGE, SERVICE, ENDPOINT, FEATURE, INTEGRATION
    description = Column(Text, nullable=True)
    url_path = Column(String(300), nullable=True)
    api_endpoint = Column(String(300), nullable=True)
    feature_flag = Column(String(100), nullable=True)
    linked_endpoints = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_wmn_category", "category"),
        Index("idx_wmn_status", "status"),
    )


class WorkflowMapEdge(Base):
    """An edge connecting two nodes in the workflow map."""
    __tablename__ = "workflow_map_edges"

    edge_id = Column(String(100), primary_key=True)
    source_node_id = Column(String(100), ForeignKey("workflow_map_nodes.node_id"), nullable=False)
    target_node_id = Column(String(100), ForeignKey("workflow_map_nodes.node_id"), nullable=False)
    flow_type = Column(String(30), nullable=False)  # Same as node category enum
    direction = Column(String(20), nullable=False, default="DIRECTED")  # DIRECTED, BIDIRECTIONAL
    label = Column(String(200), nullable=True)
    is_critical_path = Column(Boolean, default=False)
    condition = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_wme_source", "source_node_id"),
        Index("idx_wme_target", "target_node_id"),
    )


class WorkflowMapStatusHistory(Base):
    """Audit trail of status changes on workflow map nodes."""
    __tablename__ = "workflow_map_status_history"

    history_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id = Column(String(100), ForeignKey("workflow_map_nodes.node_id"), nullable=False)
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    changed_by = Column(String(100), nullable=False, default="owner")
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_wmsh_node", "node_id"),
    )
