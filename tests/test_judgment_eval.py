import json
import unittest
from supportpilot.judgment_eval import score, summarize


def example(task="answerability", positive=True):
    payload = {"policies": [{"id": "p"}], "snippets": [{"snippet_id": "p:s0"}, {"snippet_id": "p:s1"}]}
    target = ({"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["p"], "missing_fields": []}
              if positive else {"has_answering_policy": False})
    if task == "direct_evidence":
        target = {"directly_supported": True, "snippet_ids": ["p:s0"]} if positive else {"directly_supported": False}
    return {"id": "a", "task": task, "messages": [{"role": "system", "content": "rules"},
            {"role": "user", "content": json.dumps(payload)}, {"role": "assistant", "content": json.dumps(target)}]}


class JudgmentEvalTests(unittest.TestCase):
    def test_positive_and_negative_decisions(self):
        for task in ("answerability", "direct_evidence"):
            for positive in (True, False):
                row = example(task, positive)
                result = score(row, row["messages"][2]["content"])
                self.assertTrue(result["passed"])
                self.assertEqual(result["confusion"], "tp" if positive else "tn")

    def test_invalid_json_never_counts_as_correct_negative(self):
        for raw in ("nonsense", '[]', '{"has_answering_policy":0}', '{"has_answering_policy":false,"has_answering_policy":true}', '{"has_answering_policy":false} prose'):
            result = score(example(positive=False), raw)
            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["decision"])
            self.assertEqual(result["confusion"], "invalid")

    def test_reference_ids_and_provenance_are_separate(self):
        row = example("direct_evidence")
        alternative = score(row, '{"directly_supported":true,"snippet_ids":["p:s1"]}')
        self.assertTrue(alternative["checks"]["schema"])
        self.assertTrue(alternative["checks"]["decision"])
        self.assertFalse(alternative["checks"]["reference_ids"])
        invented = score(row, '{"directly_supported":true,"snippet_ids":["fake"]}')
        self.assertFalse(invented["checks"]["schema"])

    def test_wrong_boolean_and_false_positive(self):
        self.assertEqual(score(example(), '{"has_answering_policy":false}')["confusion"], "fn")
        raw = example()["messages"][2]["content"]
        self.assertEqual(score(example(positive=False), raw)["confusion"], "fp")

    def test_truncation_duplicates_and_extra_keys_fail(self):
        row = example("direct_evidence")
        self.assertFalse(score(row, row["messages"][2]["content"], truncated=True)["passed"])
        self.assertFalse(score(row, '{"directly_supported":true,"snippet_ids":["p:s0","p:s0"]}')["passed"])
        self.assertFalse(score(example(positive=False), '{"has_answering_policy":false,"supporting_ids":[]}')["passed"])
        self.assertTrue(score(row, '```json\n' + row["messages"][2]["content"] + '\n```')["passed"])

    def test_summary_uses_positive_only_id_denominator(self):
        records = []
        for positive in (True, False):
            row = example(positive=positive)
            records.append({"task": "answerability", "elapsed_ms": 10 if positive else 20, **score(row, row["messages"][2]["content"])})
        summary = summarize(records)
        self.assertEqual(summary["all"]["metrics"]["reference_ids"]["total"], 1)
        self.assertEqual(summary["all"]["metrics"]["decision"]["total"], 2)
        self.assertEqual(summary["all"]["latency_ms"]["p50"], 15)
        self.assertEqual(summary["by_task"]["direct_evidence"]["total"], 0)
