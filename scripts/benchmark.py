"""python -m scripts.benchmark --suite rules|model --url URL"""
import argparse
import hashlib
import json
import math
import platform
import time
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from supportpilot.core import DATA, answer
from supportpilot.refund import decide, today_kst

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_VERSION = "3.0"


def outcome_category(result):
    if result.get("reason") == "generation_or_validation_failed" or result.get("diagnostics"):
        return "internal_error_abstention"
    if result.get("status") == "abstained":
        if result.get("reason") == "no_answering_policy":
            return "policy_absence_abstention"
        if result.get("reason") == "no_retrieval_evidence":
            return "retrieval_abstention"
        return "unclassified_abstention"
    return "answered_or_clarified"


def forbidden_assertion_absent(text, term):
    """Conservative lexical exception, not a general semantic classifier."""
    matches = list(re.finditer(re.escape(term), text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        suffix = re.split(r"[.!?\n]", text[match.end():end], maxsplit=1)[0].strip()
        # Only recognize explicit denial forms; ambiguous mentions still fail.
        if not re.fullmatch(r"(?:이|은|는|동안|\s)*\s*(?:유효하지 않습니다|유효한 것이 아닙니다|유효하다고 (?:답변할|말할) 수 없습니다|이?\s*아닙니다)", suffix):
            return False
    return True


def latency_summary(rows):
    def summarize(group):
        values = [row["elapsed_ms"] for row in group]
        return {"count": len(values), "p50_ms": percentile(values, .5), "p95_ms": percentile(values, .95)}
    return {
        "all_requests": summarize(rows),
        "local_llm_responses": summarize([r for r in rows if r.get("response", {}).get("mode") == "local_llm"]),
        "non_llm_responses": summarize([r for r in rows if "response" in r and r["response"].get("mode") != "local_llm"]),
        "request_errors": summarize([r for r in rows if "error" in r]),
    }


def materialize(case, today):
    facts = dict(case.get("facts", {}))
    if "payment_days_ago" in facts:
        facts["payment_date"] = (today - timedelta(days=facts.pop("payment_days_ago"))).isoformat()
    body = {"question": case["question"]}
    if case["suite"] == "rules":
        body["refund_facts"] = facts
    return body


def score(case, result, documents):
    checks = {"status": result.get("status") == case["status"]}
    checks["no_internal_error"] = outcome_category(result) != "internal_error_abstention"
    if case["status"] == "abstained":
        checks["normal_abstention"] = outcome_category(result) in {"policy_absence_abstention", "retrieval_abstention"}
    if "reason" in case:
        checks["reason"] = result.get("reason") == case["reason"]
    if "required_fields" in case:
        checks["missing_fields"] = sorted(result.get("required_fields", [])) == sorted(case["required_fields"])
    citations = result.get("citations", [])
    checks["expected_citation"] = (not citations) if case["citation"] is None else any(c.get("id") == case["citation"] for c in citations)
    allowed = {d["id"]: d for d in documents}
    checks["quote_provenance"] = all(c.get("id") in allowed and isinstance(c.get("quote"), str) and bool(c["quote"].strip()) and c["quote"] in allowed[c["id"]]["text"] for c in citations)
    text = result.get("answer", "")
    checks["required_phrases"] = all(phrase in text for phrase in case.get("must_include", []))
    checks["forbidden_phrases"] = all(phrase not in text for phrase in case.get("must_not_include", []))
    if "must_not_assert" in case:
        checks["unsupported_assertions"] = all(forbidden_assertion_absent(text, phrase) for phrase in case["must_not_assert"])
    if case["suite"] == "rules":
        checks["execution_mode"] = result.get("mode") == "policy_rule"
    else:
        checks["execution_mode"] = result.get("mode") == "local_llm" or (case["citation"] is None and result.get("status") == "abstained")
    return checks


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)] if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["rules", "model"], required=True)
    parser.add_argument("--url", help="Application API base URL, e.g. http://127.0.0.1:8018")
    parser.add_argument("--date", type=date.fromisoformat, help="Fixed date for in-process rules only")
    parser.add_argument("--output", type=Path, default=ROOT / "reports")
    parser.add_argument("--dataset", choices=["development", "validation", "final"], default="development")
    parser.add_argument("--expected-prompt-version", help="Require the running API prompt version and configured LLM")
    args = parser.parse_args()
    runtime_health = None
    if args.expected_prompt_version:
        if not args.url:
            parser.error("expected-prompt-version requires --url")
        with urlopen(args.url.rstrip("/") + "/health", timeout=30) as response:
            runtime_health = json.load(response)
        if runtime_health.get("prompt_version") != args.expected_prompt_version or not runtime_health.get("model_server_configured"):
            parser.error("API prompt version or configured model does not match expected runtime")
    if args.date and (args.url or args.suite != "rules"):
        parser.error("--date is supported only for in-process rules")
    if args.dataset != "development" and args.suite == "rules":
        parser.error("validation dataset currently contains model cases only")
    today = args.date or today_kst()
    dataset = ROOT / {"development": "data/benchmark.jsonl", "validation": "data/benchmark_validation.jsonl", "final": "data/benchmark_final.jsonl"}[args.dataset]
    if args.dataset == "final":
        manifest = json.loads((ROOT / "data/final_manifest.json").read_text(encoding="utf-8"))
        if hashlib.sha256(dataset.read_bytes()).hexdigest() != manifest["sha256"]:
            parser.error("Final dataset changed; restore frozen dataset before evaluation")
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    documents = json.loads(DATA.read_text(encoding="utf-8"))
    refund = next(d for d in documents if d["id"] == "refund-v1")
    rows = []
    for case in cases:
        if case["suite"] != args.suite:
            continue
        body = materialize(case, today)
        started = time.perf_counter()
        try:
            if args.url:
                req = Request(args.url.rstrip("/") + "/api/questions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=300) as response:
                    result = json.load(response)
            elif args.suite == "rules":
                result = decide(refund, body["refund_facts"], today)
            else:
                result = answer(body["question"])
            checks = score(case, result, documents)
            row = {"id": case["id"], "request": body, "response": result, "outcome_category": outcome_category(result), "checks": checks, "passed": all(checks.values())}
        except Exception as exc:
            row = {"id": case["id"], "request": body, "passed": False, "error": f"{type(exc).__name__}: {exc}"}
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        rows.append(row)
    report = {
        "suite": args.suite, "date_kst": today.isoformat(), "url": args.url,
        "python": platform.python_version(),
        "evaluator_version": EVALUATOR_VERSION,
        "runtime_health": runtime_health,
        "dataset_split": args.dataset, "dataset_path": dataset.name,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "policies_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
        "total": len(rows), "passed": sum(r["passed"] for r in rows),
        "outcome_counts": dict(Counter(r.get("outcome_category", "request_error") for r in rows)),
        "p50_ms": percentile([r["elapsed_ms"] for r in rows], .5),
        "p95_ms": percentile([r["elapsed_ms"] for r in rows], .95),
        "latency_groups": latency_summary(rows),
        "failure_stages": dict(Counter(r.get("response", {}).get("diagnostics", {}).get("failed_stage", "request_error" if "error" in r else "evaluation_checks") for r in rows if not r["passed"])),
        "limitations": "Small development regression set; phrase checks are proxies, not semantic factuality. Sequential end-to-end latency includes warmup and failures. No TTFT or VRAM measurement.",
        "cases": rows,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / f"{args.suite}-{args.dataset}-{time.time_ns()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    groups = "\n".join(f"- {name}: n={group['count']}, P50={group['p50_ms']} ms, P95={group['p95_ms']} ms" for name, group in report["latency_groups"].items())
    path.with_suffix(".md").write_text(f"# {args.suite} evaluation\n\nEvaluator: {EVALUATOR_VERSION}\n\nPassed: {report['passed']}/{report['total']}\n\nOutcomes: {json.dumps(report['outcome_counts'], ensure_ascii=False)}\n\n{groups}\n\n{report['limitations']}\n\n" + "\n".join(f"- {r['id']}: {'PASS' if r['passed'] else 'FAIL'}" for r in rows), encoding="utf-8")
    print(f"{report['passed']}/{report['total']} passed. Report: {path}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
