import json
from pathlib import Path
from supportpilot.core import answer

root = Path(__file__).resolve().parents[1]
rows = []
for line in (root / "data/eval.jsonl").read_text(encoding="utf-8").splitlines():
    case = json.loads(line)
    result = answer(case["question"])
    actual = result["citations"][0]["id"] if result["citations"] else None
    rows.append({**case, "actual_id": actual, "passed": actual == case["expected_id"]})
report = {"label": "4-case smoke evaluation; not model quality evidence", "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows}
print(json.dumps(report, ensure_ascii=False, indent=2))
