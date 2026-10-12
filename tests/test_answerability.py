import unittest
from unittest.mock import patch
from supportpilot.generation import assess_answerability, generate

DOCS = [{"id": "p1", "title": "policy", "version": "1", "text": "링크는 30분 동안 유효합니다."}]


class AnswerabilityTests(unittest.TestCase):
    def test_no_policy_skips_generation_and_separates_review(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": False}) as request:
            result = generate("API key?", DOCS)
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["reviewed_documents"][0]["id"], "p1")
        request.assert_called_once()

    def test_supported_query_generates_grounded_answer(self):
        with patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["p1"], "missing_fields": []},
            {"directly_supported": True, "snippet_ids": ["p1:s0"]},
            {"status": "draft", "answer": "30분", "evidence": [{"id": "p1", "quote": "30분"}]},
        ]) as request:
            result = generate("유효기간?", DOCS)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(request.call_count, 3)

    def test_missing_facts_requires_named_fields(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": True, "needs_user_facts": True, "supporting_ids": ["p1"], "missing_fields": []}):
            with self.assertRaises(ValueError):
                assess_answerability("question", DOCS)

    def test_unknown_source_rejected(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["invented"], "missing_fields": []}):
            with self.assertRaises(ValueError):
                assess_answerability("question", DOCS)

    def test_no_policy_discards_inapplicable_source_fields(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": False, "supporting_ids": ["p1"]}):
            result = assess_answerability("question", DOCS)
        self.assertEqual(result["supporting_ids"], [])
        self.assertEqual(result["decision"], "no_policy")

    def test_string_boolean_rejected(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": "false"}):
            with self.assertRaises(ValueError):
                assess_answerability("question", DOCS)

    def test_true_without_evidence_is_error_not_policy_absence(self):
        with patch("supportpilot.generation.request_completion", return_value={"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": [], "missing_fields": []}):
            with self.assertRaises(ValueError):
                assess_answerability("question", DOCS)
