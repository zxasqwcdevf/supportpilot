import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from supportpilot import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "runtime"
        test_root.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=test_root)
        self.env = patch.dict(os.environ, {"SUPPORTPILOT_DB": self.directory.name + "/test.sqlite3"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def create(self, status="draft"):
        return store.create_case({"question": "테스트"}, {"status": status, "answer": "original", "citations": []})

    def test_edit_preserves_original_and_survives_connections(self):
        item = self.create()
        store.review_case(item["id"], "approved", "reviewer", "edited")
        saved = store.get_case(item["id"])
        self.assertEqual(saved["response"]["answer"], "original")
        self.assertEqual(saved["review"]["final_answer"], "edited")
        self.assertEqual(store.list_cases()[0]["review_status"], "approved")

    def test_second_review_conflicts(self):
        item = self.create()
        store.review_case(item["id"], "rejected", "reviewer")
        with self.assertRaises(RuntimeError):
            store.review_case(item["id"], "approved", "reviewer", "edited")

    def test_withheld_response_requires_edited_answer(self):
        item = self.create("abstained")
        with self.assertRaises(ValueError):
            store.review_case(item["id"], "approved", "reviewer")
        self.assertEqual(store.get_case(item["id"])["review_status"], "pending")
        with self.assertRaises(ValueError):
            store.review_case(item["id"], "approved", "reviewer", "original")

    def test_unknown_case_not_found(self):
        with self.assertRaises(KeyError):
            store.get_case("unknown")
