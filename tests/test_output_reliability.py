import os
import unittest
from unittest.mock import patch
from supportpilot.core import answer
from supportpilot.generation import parse_model_json, PipelineError, generate


class OutputReliabilityTests(unittest.TestCase):
    def test_discount_does_not_enter_refund_rule(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.core.generate", return_value={"status": "abstained", "reason": "no_answering_policy"}) as model:
            result = answer("연간 결제 시 할인율이 몇 퍼센트인지 알려주세요")
        model.assert_called_once()
        self.assertEqual(result["reason"], "no_answering_policy")

    def test_refund_still_uses_rule(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.core.generate") as model:
            self.assertEqual(answer("연간 결제 환불해주세요")["mode"], "policy_rule")
        model.assert_not_called()

    def test_whole_fence_and_plain_object(self):
        for text in ['{"status":"draft"}', '```json\n{"status":"draft"}\n```']:
            self.assertEqual(parse_model_json(text)["status"], "draft")

    def test_prose_and_truncation_stay_errors(self):
        for text in ['설명 {"status":"draft"}', '{"status":']:
            with self.assertRaises(PipelineError) as caught:
                parse_model_json(text, "length")
            self.assertEqual(caught.exception.details["finish_reason"], "length")
            self.assertIn("json_error_position", caught.exception.details)

    def test_array_is_not_object(self):
        with self.assertRaises(PipelineError):
            parse_model_json('[]')

    def test_generation_receives_assessment(self):
        docs = [{"id": "p", "title": "policy", "version": "1", "text": "30분"}]
        with patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["p"], "missing_fields": []},
            {"directly_supported": True, "snippet_ids": ["p:s0"]},
            {"status": "draft", "answer": "30분", "evidence": [{"id": "p", "quote": "30분"}]},
        ]) as request:
            generate("유효기간", docs)
        self.assertIn('"expected_status": "draft"', request.call_args.args[0][1]["content"])
