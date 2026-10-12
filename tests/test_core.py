import unittest
from supportpilot.core import answer


class GroundingTests(unittest.TestCase):
    def test_unknown_abstains_without_citation(self):
        result = answer("달에 서버 설치")
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["citations"], [])

    def test_answer_is_exact_source_quote(self):
        result = answer("연간 환불")
        self.assertEqual(result["answer"], result["citations"][0]["quote"])

    def test_invalid_input(self):
        for text in ["", "   ", "a" * 2001]:
            with self.assertRaises(ValueError):
                answer(text)
