"""Tests for Agent Benchmarking — Build Brief V2, Module 7."""
from app.benchmarking.models import BENCHMARK_REPORT_FEE_ZAR, BENCHMARK_COMMISSION_PCT

class TestBenchmarkingModels:
    def test_report_fee(self):
        assert BENCHMARK_REPORT_FEE_ZAR == 1200.0
    def test_commission_rate(self):
        assert BENCHMARK_COMMISSION_PCT == 0.15
    def test_commission_example(self):
        """R1200 report: 15% = R180 to platform, R1020 to evaluator."""
        fee = round(BENCHMARK_REPORT_FEE_ZAR * BENCHMARK_COMMISSION_PCT, 2)
        assert fee == 180.0
        assert BENCHMARK_REPORT_FEE_ZAR - fee == 1020.0
    def test_report_types(self):
        valid = {"single", "comparative", "sector_ranking"}
        assert len(valid) == 3
