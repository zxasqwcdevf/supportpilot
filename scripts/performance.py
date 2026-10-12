"""Local-only sequential/concurrent API latency measurements."""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from scripts.benchmark import percentile, outcome_category

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ["비밀번호 재설정 링크 유효기간은?", "Pro 요금제 가격과 팀원 수는?", "SAML 로그인 연결 방법은?"]


def measure(url, question, index):
    start = time.perf_counter()
    row = {"index": index, "question": question}
    try:
        req = Request(url.rstrip("/") + "/api/questions", data=json.dumps({"question": question}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=300) as response:
            result = json.load(response)
        row.update({"status": result.get("status"), "mode": result.get("mode"), "reason": result.get("reason"), "category": outcome_category(result), "stage_ms": result.get("stage_ms"), "prompt_version": result.get("prompt_version")})
    except Exception as exc:
        row.update({"category": "request_error", "error": type(exc).__name__})
    row["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return row


def summary(rows, elapsed):
    successful = [r for r in rows if r["category"] not in {"request_error", "internal_error_abstention", "unclassified_abstention"}]
    values = [r["elapsed_ms"] for r in successful]
    return {"requests": len(rows), "completed_without_pipeline_error": len(successful), "errors": len(rows) - len(successful), "successful_p50_ms": percentile(values, .5), "successful_p95_ms": percentile(values, .95), "all_p95_ms": percentile([r["elapsed_ms"] for r in rows], .95), "wall_seconds": round(elapsed, 3), "completed_requests_per_second": round(len(successful) / elapsed, 3) if elapsed else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8018")
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4])
    parser.add_argument("--label", choices=["transformers", "vllm"], default="transformers")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Performance harness targets localhost only")
    if not 1 <= args.requests <= 100 or any(n < 1 or n > 8 for n in args.concurrency):
        parser.error("Use 1..100 requests and concurrency 1..8")
    with urlopen(args.url.rstrip("/") + "/health", timeout=10) as response:
        health = json.load(response)
    if not health.get("model_server_configured"):
        parser.error("API model server is not configured; refusing baseline-only performance run")
    report = {"backend_label": args.label, "api_health": health, "url": args.url, "question_mix": QUESTIONS, "initial_probe": measure(args.url, QUESTIONS[0], -1), "warmups": [measure(args.url, question, -1) for question in QUESTIONS], "runs": {}, "limitations": "Initial probe is first measured request, not cold when startup warmup is enabled. End-to-end time includes queueing. Transformers lock serializes generation; vLLM behavior must be measured. Backend label is user supplied, not auto-detected. No TTFT/VRAM measurement. Repeated prompts may benefit from prefix caching; not unseen-query throughput. Completion is not quality correctness."}
    for concurrency in args.concurrency:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(measure, args.url, QUESTIONS[i % len(QUESTIONS)], i) for i in range(args.requests)]
            rows = [future.result() for future in as_completed(futures)]
        report["runs"][str(concurrency)] = {"summary": summary(rows, time.perf_counter() - start), "requests": sorted(rows, key=lambda r: r["index"])}
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    path = directory / f"performance-{args.label}-{time.time_ns()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value["summary"] for key, value in report["runs"].items()}, indent=2))
    print(path)
    if any(run["summary"]["errors"] for run in report["runs"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
