"""Training Data & Fine-Tuning Marketplace models.

Build Brief V2, Module 2: Operators package and sell blockchain-verified
fine-tuning datasets with immutable provenance. Commission: 15% to platform.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base

TRAINING_DATA_COMMISSION_PCT = 0.15  # 15% to platform, 85% to seller


class TrainingDataset(Base):
    __tablename__ = "training_datasets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    dataset_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    domain_tags = Column(JSON, nullable=False)
    record_count = Column(Integer, nullable=False)
    source_engagement_ids = Column(JSON, default=list)
    pricing_model = Column(String(20), nullable=False)  # per_record|flat|subscription
    price_per_record = Column(Float, nullable=True)
    flat_price = Column(Float, nullable=True)
    licence_type = Column(String(30), nullable=False)  # commercial|research|non_commercial
    data_format = Column(String(20), nullable=False)   # jsonl|csv|parquet
    quality_score = Column(Float, nullable=True)
    provenance_hash = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DatasetPurchase(Base):
    __tablename__ = "dataset_purchases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String, nullable=False)
    buyer_operator_id = Column(String, nullable=False)
    licence_granted = Column(String(30), nullable=False)
    amount_paid = Column(Float, nullable=False)
    download_token = Column(String(64), nullable=True)
    downloaded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
