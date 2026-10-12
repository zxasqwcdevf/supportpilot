import unittest
from datetime import date
from scripts.benchmark import materialize, percentile, score, forbidden_assertion_absent, latency_summary, outcome_category


class BenchmarkTests(unittest.TestCase):
    def test_error_abstention_never_passes(self):
        case = {"suite": "model", "status": "abstained", "citation": None}
        result = {"status": "abstained", "mode": "local_llm", "citations": [], "answer": "확인 필요", "reason": "generation_or_validation_failed"}
        self.assertFalse(all(score(case, result, []).values()))
        self.assertEqual(outcome_category(result), "internal_error_abstention")

    def test_normal_policy_absence_passes(self):
        case = {"suite": "model", "status": "abstained", "citation": None}
        result = {"status": "abstained", "mode": "local_llm", "citations": [], "answer": "정책 없음", "reason": "no_answering_policy"}
        self.assertTrue(all(score(case, result, []).values()))

    def test_unclassified_abstention_fails(self):
        checks = score({"suite": "model", "status": "abstained", "citation": None}, {"status": "abstained", "mode": "local_llm", "citations": [], "answer": "보류"}, [])
        self.assertFalse(checks["normal_abstention"])
    def test_relative_dates(self):
        body = materialize({"suite": "rules", "question": "환불", "facts": {"payment_days_ago": 7, "usage_history": False}}, date(2026, 10, 10))
        self.assertEqual(body["refund_facts"]["payment_date"], "2026-10-03")
        self.assertIs(body["refund_facts"]["usage_history"], False)

    def test_baseline_cannot_claim_model_pass(self):
        checks = score({"suite": "model", "status": "draft", "citation": "x"}, {"status": "draft", "answer": "text", "mode": "extractive_baseline", "citations": [{"id": "x", "quote": "text"}]}, [{"id": "x", "text": "text"}])
        self.assertFalse(checks["execution_mode"])

    def test_latency_percentile(self):
        self.assertEqual(percentile([10, 1, 2], .95), 10)

    def test_explicit_denial_is_not_assertion(self):
        self.assertTrue(forbidden_assertion_absent("30분 동안 유효합니다. 24시간 유효하다고 답변할 수 없습니다.", "24시간"))
        self.assertTrue(forbidden_assertion_absent("링크는 24시간 유효하지 않습니다.", "24시간"))

    def test_assertion_and_mixed_claims_fail(self):
        for text in ["24시간 유효합니다.", "24시간 유효합니다. 하지만 24시간 유효하지 않습니다.", "24시간이 아니라 30분입니다."]:
            self.assertFalse(forbidden_assertion_absent(text, "24시간"))

    def test_latency_excludes_retrieval_abstention(self):
        groups = latency_summary([
            {"elapsed_ms": 2000, "response": {"mode": "local_llm"}},
            {"elapsed_ms": 1, "response": {"mode": "extractive_baseline"}},
            {"elapsed_ms": 99, "error": "offline"},
        ])
        self.assertEqual(groups["local_llm_responses"]["count"], 1)
        self.assertEqual(groups["local_llm_responses"]["p50_ms"], 2000)
        self.assertEqual(groups["request_errors"]["count"], 1)
