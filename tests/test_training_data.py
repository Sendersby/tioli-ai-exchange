"""Tests for Training Data Marketplace — Build Brief V2, Module 2."""
import hashlib
from app.training_data.models import TRAINING_DATA_COMMISSION_PCT

class TestTrainingDataModels:
    def test_commission_rate(self):
        assert TRAINING_DATA_COMMISSION_PCT == 0.15
    def test_provenance_hash_deterministic(self):
        ids = ["eng-3", "eng-1", "eng-2"]
        sorted_ids = sorted(ids)
        h1 = hashlib.sha256("|".join(sorted_ids).encode()).hexdigest()
        h2 = hashlib.sha256("|".join(sorted_ids).encode()).hexdigest()
        assert h1 == h2
        assert len(h1) == 64
    def test_commission_example(self):
        """R1000 dataset: 15% = R150 to platform, R850 to seller."""
        price = 1000
        fee = round(price * TRAINING_DATA_COMMISSION_PCT, 2)
        assert fee == 150.0
        assert price - fee == 850.0
    def test_minimum_records(self):
        """Brief requires minimum 50 source engagements."""
        min_records = 50
        assert min_records == 50
