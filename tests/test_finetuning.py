import copy
import json
import tempfile
import unittest
from pathlib import Path
from supportpilot.finetuning import encode_example, pad_examples, load_training_splits


class Tokenizer:
    def apply_chat_template(self, conversation, add_generation_prompt, **kwargs):
        return [10, 11, 12] if add_generation_prompt else [10, 11, 12, 20, 21, 99]


class FinetuningTests(unittest.TestCase):
    def test_only_assistant_and_end_tokens_have_loss(self):
        row = {"id": "a", "messages": [{}, {}, {}]}
        encoded = encode_example(Tokenizer(), row, 10)
        self.assertEqual(encoded["labels"], [-100, -100, -100, 20, 21, 99])
        with self.assertRaisesRegex(ValueError, "no truncation"):
            encode_example(Tokenizer(), row, 5)

    def test_template_mismatch_fails(self):
        class Broken(Tokenizer):
            def apply_chat_template(self, conversation, add_generation_prompt, **kwargs):
                return [0, 1] if add_generation_prompt else [0, 2, 3]
        with self.assertRaisesRegex(ValueError, "prefix mismatch"):
            encode_example(Broken(), {"id": "a", "messages": [{}, {}, {}]}, 10)

    def test_padding_never_contributes_to_loss(self):
        a = {"input_ids": [1, 2], "attention_mask": [1, 1], "labels": [-100, 2]}
        b = {"input_ids": [3], "attention_mask": [1], "labels": [3]}
        self.assertEqual(pad_examples([a, b], 99), {"input_ids": [[1, 2], [3, 99]], "attention_mask": [[1, 1], [1, 0]], "labels": [[-100, 2], [3, -100]]})

    def test_load_does_not_open_test_and_rejects_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"counts": {"train": 1, "validation": 1}, "groups": {"train": ["a"], "validation": ["b"]}}
            (root / "manifest.json").write_text(json.dumps(manifest))
            row = {"id": "train-a", "group_id": "a", "messages": [{"role": "system", "content": "rules"}, {"role": "user", "content": json.dumps({"question": "one"})}, {"role": "assistant", "content": "{}"}]}
            (root / "train.jsonl").write_text(json.dumps(row))
            other = copy.deepcopy(row)
            other["group_id"] = "b"
            other["id"] = "validation-b"
            other["messages"][1]["content"] = json.dumps({"question": "two"})
            (root / "validation.jsonl").write_text(json.dumps(other))
            self.assertEqual(len(load_training_splits(root)[0]["train"]), 1)
            other["messages"][1]["content"] = json.dumps({"question": "one"})
            (root / "validation.jsonl").write_text(json.dumps(other))
            with self.assertRaisesRegex(ValueError, "Question leakage"):
                load_training_splits(root)
