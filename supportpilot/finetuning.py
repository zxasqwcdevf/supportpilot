"""Assistant-only targets for the two judgment tasks (no GPU imports)."""
import hashlib
import json
from pathlib import Path


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_training_splits(directory, include_test=False):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    splits = {}
    for name in (("train", "validation", "test") if include_test else ("train", "validation")):
        rows = [json.loads(line) for line in (directory / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows or len(rows) != manifest["counts"][name]:
            raise ValueError(f"Invalid {name} count")
        if sorted({row["group_id"] for row in rows}) != manifest["groups"][name]:
            raise ValueError(f"Invalid {name} groups")
        for row in rows:
            conversation = row["messages"]
            if [m["role"] for m in conversation] != ["system", "user", "assistant"]:
                raise ValueError("Expected one system/user/assistant turn")
            payload = json.loads(conversation[1]["content"])
            if not isinstance(payload.get("question"), str):
                raise ValueError("Missing question")
            if not isinstance(json.loads(conversation[2]["content"]), dict):
                raise ValueError("Target must be a JSON object")
        splits[name] = rows
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if set(manifest["groups"][first]) & set(manifest["groups"].get(second, [])):
            raise ValueError("Family leakage")
    identities = [row["id"] for rows in splits.values() for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate record IDs")
    questions = lambda rows: {''.join(json.loads(r["messages"][1]["content"])["question"].lower().split()) for r in rows}
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if second in splits and questions(splits[first]) & questions(splits[second]):
            raise ValueError("Question leakage")
    # Training/validation callers never open test unless explicitly requested.
    return splits, manifest


def encode_example(tokenizer, row, max_length):
    conversation = row["messages"]
    options = dict(tokenize=True, enable_thinking=False)
    prefix = tokenizer.apply_chat_template(conversation[:-1], add_generation_prompt=True, **options)
    full = tokenizer.apply_chat_template(conversation, add_generation_prompt=False, **options)
    if full[:len(prefix)] != prefix:
        raise ValueError("Chat template prefix mismatch; cannot safely mask prompt")
    if len(full) > max_length:
        raise ValueError(f"{row['id']}: {len(full)} tokens exceeds {max_length}; increase --max-length (no truncation)")
    if len(full) <= len(prefix):
        raise ValueError("Empty assistant target")
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": [-100] * len(prefix) + full[len(prefix):]}


def pad_examples(examples, pad_id):
    length = max(len(row["input_ids"]) for row in examples)
    return {key: [row[key] + [pad] * (length - len(row[key])) for row in examples]
            for key, pad in (("input_ids", pad_id), ("attention_mask", 0), ("labels", -100))}
