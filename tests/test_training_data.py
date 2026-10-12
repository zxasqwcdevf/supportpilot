import unittest
from supportpilot.training_data import grouped_split, validate_record


def record(group, variant, positive):
    return {"id": f"{group}-{variant}", "group_id": group, "question": f"{group} question {variant}", "task": "answerability", "policies": [{"id": "p", "text": "policy"}], "target": {"has_answering_policy": True, "needs_user_facts": False, "supporting_ids": ["p"], "missing_fields": []} if positive else {"has_answering_policy": False}}


class TrainingDataTests(unittest.TestCase):
    def test_variants_stay_in_same_split(self):
        rows = [record(f"group-{i}", v, i < 10) for i in range(20) for v in range(2)]
        split = grouped_split(rows)
        assigned = {}
        for name, subset in split.items():
            for row in subset:
                self.assertEqual(assigned.setdefault(row["group_id"], name), name)
        self.assertEqual(len(assigned), 20)
        self.assertEqual(split, grouped_split(rows))

    def test_insufficient_reviewed_data_blocks_split(self):
        with self.assertRaises(ValueError):
            grouped_split([])

    def test_invalid_source_rejected(self):
        row = record("x", 0, True)
        row["target"]["supporting_ids"] = ["invented"]
        with self.assertRaises(ValueError):
            validate_record(row)

    def test_exact_question_leakage_rejected(self):
        rows = [record(f"group-{i}", 0, i < 10) for i in range(20)]
        for row in rows:
            row["question"] = "same question"
        with self.assertRaises(ValueError):
            grouped_split(rows)
