"""Narrow invoice evidence to the receipt-download sentence; preserve other reviews."""
import json
from datetime import datetime, timezone
from supportpilot.generation import source_snippets
from supportpilot.training_data import validate_record
from scripts.training_data import CANDIDATES, REVIEWS, read_rows, write_jsonl


def repair(rows):
    changed = 0
    for row in rows:
        if row["group_id"] != "family-03":
            continue
        if row["task"] == "direct_evidence":
            document = next(doc for doc in row["policies"] if doc["id"] == "invoice-v1")
            snippets = source_snippets([document])
            receipt = [s["snippet_id"] for s in snippets if "PDF" in s["quote"] and "영수증" in s["quote"]]
            if len(receipt) != 1:
                raise ValueError("Expected exactly one receipt-download sentence; no files written")
            target = {"directly_supported": True, "snippet_ids": receipt}
            if row["target"] != target:
                row["target"] = target
                changed += 1
        validate_record(row)
    return changed


def main():
    rows = read_rows()
    changed = repair(rows)
    if not changed:
        print("No changes needed; reviews preserved")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    reviews = json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else {}
    CANDIDATES.with_name(f"candidates.before-invoice-fix-{stamp}.jsonl").write_bytes(CANDIDATES.read_bytes())
    if REVIEWS.exists():
        REVIEWS.with_name(f"reviews.before-invoice-fix-{stamp}.json").write_bytes(REVIEWS.read_bytes())
    write_jsonl(CANDIDATES, rows)
    if "family-03" in reviews:
        del reviews["family-03"]
        REVIEWS.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {changed} evidence labels in family-03. Other reviews preserved. Inspect and review family-03 again.")


if __name__ == "__main__":
    main()
