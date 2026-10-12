import os
import unittest
from unittest.mock import patch
from supportpilot.core import answer
from supportpilot.generation import request_completion, PipelineError


class FakeResponse:
    def __enter__(self):
        from io import BytesIO
        return BytesIO(b'{"choices":[{"message":{"content":"not JSON"}}]}')

    def __exit__(self, *args):
        pass


class DiagnosticsTests(unittest.TestCase):
    def test_invalid_content_identified(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.generation.urlopen", return_value=FakeResponse()):
            with self.assertRaises(PipelineError) as caught:
                request_completion([])
        self.assertEqual(caught.exception.stage, "json_decode")

    def test_assessment_schema_error_recorded(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.generation.request_completion", return_value={"decision": "invalid"}):
            result = answer("비밀번호")
        self.assertEqual(result["diagnostics"]["failed_stage"], "answerability")
        self.assertEqual(result["diagnostics"]["error_code"], "Invalid has_answering_policy boolean")

    def test_generation_json_failure_has_stage_prefix(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["password-v1"], "missing_fields": []},
            {"directly_supported": True, "snippet_ids": ["password-v1:s0"]},
            PipelineError("json_decode", "JSONDecodeError", "model_content_not_json"),
        ]):
            result = answer("비밀번호")
        self.assertEqual(result["diagnostics"]["failed_stage"], "generation.json_decode")

    def test_status_mismatch_identified(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.generation.request_completion", side_effect=[
            {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["password-v1"], "missing_fields": []},
            {"directly_supported": True, "snippet_ids": ["password-v1:s0"]},
            {"status": "needs_information", "answer": "질문", "evidence": []},
        ]):
            result = answer("비밀번호")
        self.assertEqual(result["diagnostics"]["failed_stage"], "status_consistency")
