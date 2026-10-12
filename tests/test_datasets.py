import json
import hashlib
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def load(name):
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]


class DatasetTests(unittest.TestCase):
    def test_final_set_is_frozen_and_disjoint(self):
        manifest = json.loads((DATA / "final_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((DATA / "benchmark_final.jsonl").read_bytes()).hexdigest(), manifest["sha256"])
        rows = load("benchmark_final.jsonl")
        self.assertEqual(len(rows), manifest["cases"])
        earlier = load("benchmark.jsonl") + load("benchmark_validation.jsonl")
        self.assertFalse({r["question"] for r in rows} & {r["question"] for r in earlier})
        self.assertEqual(len(rows), len({r["id"] for r in rows}))
    def test_validation_ids_and_questions_are_distinct(self):
        for dev, val in [("retrieval_eval.jsonl", "retrieval_validation.jsonl"), ("benchmark.jsonl", "benchmark_validation.jsonl")]:
            rows = load(val)
            self.assertEqual(len(rows), len({r["id"] for r in rows}))
            self.assertFalse({r["question"] for r in rows} & {r["question"] for r in load(dev)})

    def test_expected_sources_exist(self):
        ids = {d["id"] for d in json.loads((DATA / "policies.json").read_text(encoding="utf-8"))}
        for row in load("retrieval_validation.jsonl"):
            self.assertTrue(set(row["relevant"]) <= ids)
        for row in load("benchmark_validation.jsonl"):
            self.assertTrue(row["citation"] is None or row["citation"] in ids)
