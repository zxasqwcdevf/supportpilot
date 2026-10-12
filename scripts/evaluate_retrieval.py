import argparse
import hashlib
import json
import time
import os
from pathlib import Path
from supportpilot.core import DATA
from supportpilot.retrieval import retrieve, warmup
from scripts.benchmark import percentile

ROOT = Path(__file__).resolve().parents[1]


def metrics(expected, actual):
    if not expected:
        return {"negative_abstention": not actual}
    ranks = [i + 1 for i, doc in enumerate(actual) if doc in expected]
    return {"recall_at_3": len(set(expected) & set(actual)) / len(set(expected)), "reciprocal_rank": 1 / min(ranks) if ranks else 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", nargs="+", choices=["keyword", "bm25", "hybrid"], default=["keyword", "bm25"])
    parser.add_argument("--dataset", choices=["development", "validation"], default="development")
    args = parser.parse_args()
    dataset = ROOT / ("data/retrieval_validation.jsonl" if args.dataset == "validation" else "data/retrieval_eval.jsonl")
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    documents = json.loads(DATA.read_text(encoding="utf-8"))
    report = {"dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(), "policies_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(), "limitations": "Small development set. Korean character bigrams are a lexical baseline, not morphological analysis. Dense cutoff is uncalibrated. No held-out quality claim.", "methods": {}}
    report["embedding_model"] = os.getenv("SUPPORTPILOT_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    report["dense_threshold"] = float(os.getenv("SUPPORTPILOT_DENSE_THRESHOLD", "0.8"))
    report["bm25_threshold"] = float(os.getenv("SUPPORTPILOT_BM25_THRESHOLD", "2.0"))
    report["retrieval_version"] = "2.0"
    report["dataset_split"] = args.dataset
    report["dataset_path"] = dataset.name
    for method in args.methods:
        initialization_ms = 0
        if method == "hybrid":
            init_started = time.perf_counter()
            warmup(documents)
            initialization_ms = round((time.perf_counter() - init_started) * 1000, 3)
        rows = []
        for case in cases:
            start = time.perf_counter()
            hits = retrieve(case["question"], documents, method=method)
            actual = [hit["document"]["id"] for hit in hits]
            rows.append({**case, "retrieved": actual, "scores": [{k: v for k, v in hit.items() if k != "document"} for hit in hits], "metrics": metrics(case["relevant"], actual), "elapsed_ms": round((time.perf_counter() - start) * 1000, 3)})
        positives = [r for r in rows if r["relevant"]]
        negatives = [r for r in rows if not r["relevant"]]
        report["methods"][method] = {"positive_count": len(positives), "negative_count": len(negatives), "recall_at_3": sum(r["metrics"]["recall_at_3"] for r in positives) / len(positives), "mrr_at_3": sum(r["metrics"]["reciprocal_rank"] for r in positives) / len(positives), "negative_abstention_rate": sum(r["metrics"]["negative_abstention"] for r in negatives) / len(negatives), "cases": rows}
        report["methods"][method].update({"initialization_ms": initialization_ms, "warm_p50_ms": percentile([r["elapsed_ms"] for r in rows], .5), "warm_p95_ms": percentile([r["elapsed_ms"] for r in rows], .95)})
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    path = directory / f"retrieval-{args.dataset}-{time.time_ns()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({method: {k: v for k, v in value.items() if k != "cases"} for method, value in report["methods"].items()}, ensure_ascii=False, indent=2))
    print(path)


if __name__ == "__main__":
    main()
