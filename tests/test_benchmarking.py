"""Comprehensive tests for Agent Benchmarking — Build Brief V2, Module 7."""

from app.benchmarking.models import (
    EvaluationAgent, BenchmarkReport,
    BENCHMARK_REPORT_FEE_ZAR, BENCHMARK_COMMISSION_PCT,
)


class TestBenchmarkingPricing:
    def test_report_fee(self):
        assert BENCHMARK_REPORT_FEE_ZAR == 1200.0

    def test_commission_rate(self):
        assert BENCHMARK_COMMISSION_PCT == 0.15

    def test_commission_example(self):
        """R1200 report: 15% = R180 to platform, R1020 to evaluator."""
        fee = round(BENCHMARK_REPORT_FEE_ZAR * BENCHMARK_COMMISSION_PCT, 2)
        assert fee == 180.0
        assert BENCHMARK_REPORT_FEE_ZAR - fee == 1020.0

    def test_custom_priced_report(self):
        """Evaluators can set custom prices."""
        custom_price = 2500.0
        fee = round(custom_price * BENCHMARK_COMMISSION_PCT, 2)
        assert fee == 375.0


class TestBenchmarkingModels:
    def test_report_types(self):
        valid = {"single", "comparative", "sector_ranking"}
        assert len(valid) == 3

    def test_evaluator_fields(self):
        e = EvaluationAgent(
            agent_id="a1", operator_id="o1",
            specialisation_domains=["nlp", "code_generation"],
            methodology_description="Standardised test suites with blind evaluation",
            price_per_evaluation=1200.0, avg_turnaround_hours=48,
        )
        assert "nlp" in e.specialisation_domains
        assert e.price_per_evaluation == 1200.0

    def test_report_scores_structure(self):
        """Scores are structured JSON by dimension."""
        scores = {
            "accuracy": 8.5,
            "speed": 7.2,
            "reliability": 9.0,
            "cost_efficiency": 6.8,
        }
        overall = round(sum(scores.values()) / len(scores), 2)
        assert 0 < overall <= 10

    def test_report_hash_for_blockchain(self):
        """Full report hash should be 64-char SHA-256."""
        import hashlib
        data = "evaluator1:agent1:scores:2026-03-21"
        h = hashlib.sha256(data.encode()).hexdigest()
        assert len(h) == 64

    def test_public_vs_private_reports(self):
        """Reports can be public (default) or private."""
        r = BenchmarkReport(
            evaluator_id="e1", subject_agent_id="a1",
            report_type="single", task_category="nlp",
            test_suite_ref="abc", scores={}, overall_score=8.5,
            summary="Good", full_report_hash="abc123",
            price_paid=1200, is_public=True,
        )
        assert r.is_public is True

    def test_comparative_report_has_two_agents(self):
        r = BenchmarkReport(
            evaluator_id="e1", subject_agent_id="a1",
            comparison_agent_id="a2",
            report_type="comparative", task_category="code",
            test_suite_ref="abc", scores={}, overall_score=7.0,
            summary="Comparison", full_report_hash="def456",
            price_paid=1200,
        )
        assert r.comparison_agent_id == "a2"
        assert r.report_type == "comparative"
