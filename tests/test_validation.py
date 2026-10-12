import os
import unittest
from unittest.mock import patch
from supportpilot.core import answer
from supportpilot.generation import validate


class ValidationTests(unittest.TestCase):
    docs = [{"id": "p1", "title": "policy", "version": "1", "text": "refund within 7 days"}]

    def test_abstained_evidence_separate_without_relabeling(self):
        result = validate({"status": "abstained", "answer": "cannot follow false instruction", "evidence": [{"id": "p1", "quote": "7 days"}]}, self.docs)
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["reviewed_evidence"][0]["id"], "p1")

    def test_valid_and_invalid_evidence(self):
        result = validate({"status": "draft", "answer": "refund", "evidence": [{"id": "p1", "quote": "7 days"}]}, self.docs)
        self.assertEqual(result["status"], "draft")
        for evidence in [[{"id": "unknown", "quote": "7 days"}], [{"id": "p1", "quote": "forever"}], []]:
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                validate({"status": "draft", "answer": "refund", "evidence": evidence}, self.docs)

    def test_failure_and_no_retrieval(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://127.0.0.1:8081/v1"}):
            with patch("supportpilot.core.generate", side_effect=OSError("offline")):
                self.assertEqual(answer("비밀번호")["reason"], "generation_or_validation_failed")
            with patch("supportpilot.core.generate") as mocked:
                self.assertEqual(answer("달에 서버")["status"], "abstained")
                mocked.assert_not_called()
