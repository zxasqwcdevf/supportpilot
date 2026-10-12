import unittest
from datetime import date
from supportpilot.refund import decide

DOCUMENT = {"id": "refund-v1", "title": "환불", "version": "1", "text": "7일 이내이며 사용 이력이 없으면 전액 환불. 그 외 요청은 상담원 확인.", "decision": {"required_fields": ["plan", "payment_date", "usage_history"]}}
TODAY = date(2026, 10, 10)


class RefundFactsTests(unittest.TestCase):
    def evaluate(self, **changes):
        facts = {"plan": "annual", "payment_date": "2026-10-03", "usage_history": False}
        facts.update(changes)
        return decide(DOCUMENT, facts, TODAY)

    def test_day_seven_eligible(self):
        self.assertEqual(self.evaluate()["reason"], "full_refund_conditions_met")

    def test_day_eight_review(self):
        self.assertEqual(self.evaluate(payment_date="2026-10-02")["status"], "requires_review")

    def test_usage_and_monthly_review(self):
        for facts in [{"usage_history": True}, {"plan": "monthly"}]:
            result = self.evaluate(**facts)
            self.assertEqual(result["status"], "requires_review")
            self.assertNotIn("불가능", result["answer"])

    def test_only_missing_field_requested(self):
        result = self.evaluate(usage_history=None)
        self.assertEqual(result["required_fields"], ["usage_history"])

    def test_false_is_present(self):
        self.assertEqual(self.evaluate()["required_fields"], [])

    def test_future_date_corrected(self):
        result = self.evaluate(payment_date="2026-10-11")
        self.assertEqual(result["reason"], "future_payment_date")
        self.assertEqual(result["required_fields"], ["payment_date"])

    def test_same_day_eligible(self):
        self.assertEqual(self.evaluate(payment_date="2026-10-10")["status"], "draft")
