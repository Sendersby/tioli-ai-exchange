"""Training Data Marketplace service — listing, purchase, and provenance verification."""

import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.training_data.models import TrainingDataset, DatasetPurchase, TRAINING_DATA_COMMISSION_PCT

logger = logging.getLogger(__name__)


class TrainingDataService:
    async def create_dataset(
        self, db: AsyncSession, operator_id: str,
        dataset_name: str, description: str, domain_tags: list[str],
        record_count: int, source_engagement_ids: list[str],
        pricing_model: str, licence_type: str, data_format: str,
        price_per_record: float | None = None, flat_price: float | None = None,
        quality_score: float | None = None,
    ) -> dict:
        if record_count < 50:
            raise ValueError("Minimum 50 source records required")

        # Compute provenance hash from source engagement IDs
        sorted_ids = sorted(source_engagement_ids)
        provenance_hash = hashlib.sha256("|".join(sorted_ids).encode()).hexdigest()

        dataset = TrainingDataset(
            operator_id=operator_id, dataset_name=dataset_name,
            description=description, domain_tags=domain_tags,
            record_count=record_count, source_engagement_ids=source_engagement_ids,
            pricing_model=pricing_model, price_per_record=price_per_record,
            flat_price=flat_price, licence_type=licence_type,
            data_format=data_format, quality_score=quality_score,
            provenance_hash=provenance_hash,
        )
        db.add(dataset)
        await db.flush()

        return {
            "dataset_id": dataset.id, "dataset_name": dataset_name,
            "record_count": record_count, "provenance_hash": provenance_hash,
            "pricing_model": pricing_model, "licence_type": licence_type,
            "commission_pct": f"{TRAINING_DATA_COMMISSION_PCT*100:.0f}%",
        }

    async def search_datasets(
        self, db: AsyncSession, domain_tag: str | None = None,
        licence_type: str | None = None, max_price: float | None = None,
        data_format: str | None = None, limit: int = 50,
    ) -> list[dict]:
        query = select(TrainingDataset).where(TrainingDataset.is_active == True)
        if licence_type:
            query = query.where(TrainingDataset.licence_type == licence_type)
        if data_format:
            query = query.where(TrainingDataset.data_format == data_format)
        if max_price is not None:
            query = query.where(TrainingDataset.flat_price <= max_price)
        query = query.order_by(TrainingDataset.created_at.desc()).limit(limit)

        result = await db.execute(query)
        datasets = result.scalars().all()
        if domain_tag:
            datasets = [d for d in datasets if domain_tag in (d.domain_tags or [])]

        return [
            {
                "dataset_id": d.id, "dataset_name": d.dataset_name,
                "domain_tags": d.domain_tags, "record_count": d.record_count,
                "pricing_model": d.pricing_model, "flat_price": d.flat_price,
                "price_per_record": d.price_per_record,
                "licence_type": d.licence_type, "data_format": d.data_format,
                "quality_score": d.quality_score,
            }
            for d in datasets
        ]

    async def purchase(
        self, db: AsyncSession, dataset_id: str, buyer_operator_id: str,
    ) -> dict:
        ds_result = await db.execute(
            select(TrainingDataset).where(TrainingDataset.id == dataset_id)
        )
        dataset = ds_result.scalar_one_or_none()
        if not dataset or not dataset.is_active:
            raise ValueError("Dataset not found or inactive")

        amount = dataset.flat_price or (dataset.price_per_record or 0) * dataset.record_count
        platform_fee = round(amount * TRAINING_DATA_COMMISSION_PCT, 4)
        seller_receives = round(amount - platform_fee, 4)
        download_token = secrets.token_urlsafe(48)

        purchase = DatasetPurchase(
            dataset_id=dataset_id, buyer_operator_id=buyer_operator_id,
            licence_granted=dataset.licence_type, amount_paid=amount,
            download_token=download_token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(purchase)
        await db.flush()

        return {
            "purchase_id": purchase.id, "dataset_id": dataset_id,
            "amount_paid": amount, "platform_fee": platform_fee,
            "seller_receives": seller_receives,
            "download_token": download_token,
            "expires_at": str(purchase.expires_at),
        }

    async def verify_provenance(self, db: AsyncSession, dataset_id: str) -> dict | None:
        ds_result = await db.execute(
            select(TrainingDataset).where(TrainingDataset.id == dataset_id)
        )
        dataset = ds_result.scalar_one_or_none()
        if not dataset:
            return None

        return {
            "dataset_id": dataset.id, "provenance_hash": dataset.provenance_hash,
            "source_engagement_count": len(dataset.source_engagement_ids or []),
            "record_count": dataset.record_count,
            "quality_score": dataset.quality_score,
            "verifiable": True,
        }
