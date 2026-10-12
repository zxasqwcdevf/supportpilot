"""Re-score existing raw outputs; no GPU, generation, or dataset modification."""
import argparse
import json
from pathlib import Path
import time
from supportpilot.finetuning import load_training_splits, file_sha
from supportpilot.judgment_eval import score, summarize
from supportpilot.judgment_revision import revise_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--data", default="data/training/prepared")
    args = parser.parse_args()
    original = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if original["dataset_sha256"] != file_sha(Path(args.data) / "validation.jsonl"):
        parser.error("Validation dataset differs from original report")
    splits, _ = load_training_splits(args.data)
    rows, corrections = revise_rows(splits["validation"], correct_refund=True)
    by_id = {r["id"]: r for r in rows}
    cases = {}
    for mode in ("base", "adapter"):
        if {c["id"] for c in original["cases"][mode]} != set(by_id):
            parser.error("Report records do not match validation")
        cases[mode] = []
        for previous in original["cases"][mode]:
            original_target = json.loads(next(r for r in splits["validation"] if r["id"] == previous["id"])["messages"][2]["content"])
            corrected_target = json.loads(by_id[previous["id"]]["messages"][2]["content"])
            if previous["expected"] not in (original_target, corrected_target):
                parser.error("Report uses unrecognized reference labels")
            result = score(by_id[previous["id"]], previous["raw"], previous["truncated"])
            cases[mode].append({**previous, **result})
    summary = {mode: summarize(values) for mode, values in cases.items()}
    report = {**original, "evaluator_version": "judgment-comparison-1.2-rescore", "source_report": args.report,
              "source_report_sha256": file_sha(args.report), "reference_corrections": corrections,
              "summary": summary, "cases": cases, "timings_reused": True}
    # Old paired outcomes are no longer valid after changing references.
    report.pop("paired", None)
    output = Path(args.report).with_name(f"qlora-rescored-{time.time_ns()}.json")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"summary": summary, "report": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
