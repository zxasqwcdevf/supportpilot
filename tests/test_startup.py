import os
import unittest
from unittest.mock import patch
from supportpilot.startup import initialize


class StartupTests(unittest.TestCase):
    def test_disabled_does_not_call_model(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_WARMUP": "0"}), patch("supportpilot.startup.answer") as model:
            self.assertFalse(initialize()["ready"])
        model.assert_not_called()

    def test_warms_hybrid_and_model(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_WARMUP": "1", "SUPPORTPILOT_RETRIEVAL": "hybrid", "SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.startup.warmup") as search, patch("supportpilot.startup.answer", return_value={"status": "draft", "mode": "local_llm"}):
            info = initialize()
        search.assert_called_once()
        self.assertTrue(info["ready"])
        self.assertTrue(info["model_path_warmed"])

    def test_bad_model_response_fails_startup(self):
        with patch.dict(os.environ, {"SUPPORTPILOT_WARMUP": "1", "SUPPORTPILOT_RETRIEVAL": "keyword", "SUPPORTPILOT_MODEL_URL": "http://localhost:8081/v1"}), patch("supportpilot.startup.answer", return_value={"status": "abstained"}):
            with self.assertRaises(RuntimeError):
                initialize()
