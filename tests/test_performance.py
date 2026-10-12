import unittest
from scripts.performance import summary


class PerformanceTests(unittest.TestCase):
    def test_errors_excluded_from_success_latency(self):
        result = summary([{"elapsed_ms": 2000, "category": "answered_or_clarified"}, {"elapsed_ms": 1, "category": "internal_error_abstention"}], 3)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["successful_p50_ms"], 2000)

    def test_all_errors_have_no_success_latency(self):
        result = summary([{"elapsed_ms": 1, "category": "request_error"}], 1)
        self.assertIsNone(result["successful_p50_ms"])
