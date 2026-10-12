"""Strict JSON and reference-label scoring; no model dependencies."""
import json
import math
import re


def parse_object(raw):
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def string_ids(value, allowed=None, nonempty=False):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(isinstance(x, str) and x.strip() for x in value)
            and len(value) == len(set(value))
            and (allowed is None or set(value) <= allowed))


def valid_schema(value, task, payload):
    flag = "has_answering_policy" if task == "answerability" else "directly_supported"
    if type(value.get(flag)) is not bool:
        return False
    if not value[flag]:
        if set(value) == {flag}:
            return True
        if task == "answerability":
            return (set(value) == {flag, "needs_user_facts", "supporting_ids", "missing_fields"}
                    and value.get("needs_user_facts") is False
                    and value.get("supporting_ids") == [] and value.get("missing_fields") == [])
        return set(value) == {flag, "snippet_ids"} and value.get("snippet_ids") == []
    if task == "answerability":
        return (set(value) == {flag, "needs_user_facts", "supporting_ids", "missing_fields"}
                and type(value.get("needs_user_facts")) is bool
                and string_ids(value.get("supporting_ids"), {p["id"] for p in payload["policies"]}, True)
                and string_ids(value.get("missing_fields"))
                and bool(value["missing_fields"]) == value["needs_user_facts"])
    return (set(value) == {flag, "snippet_ids"}
            and string_ids(value.get("snippet_ids"), {s["snippet_id"] for s in payload["snippets"]}, True))


def score(row, raw, truncated=False):
    task = row["task"]
    if task not in ("answerability", "direct_evidence"):
        raise ValueError("Unknown judgment task")
    payload = json.loads(row["messages"][1]["content"])
    expected = parse_object(row["messages"][2]["content"])
    if not valid_schema(expected, task, payload):
        raise ValueError(f"Invalid reference label: {row['id']}")
    flag = "has_answering_policy" if task == "answerability" else "directly_supported"
    ids_key = "supporting_ids" if task == "answerability" else "snippet_ids"
    parsed, error = None, None
    try:
        parsed = parse_object(raw)
    except (ValueError, TypeError) as exc:
        error = str(exc)
    schema = parsed is not None and valid_schema(parsed, task, payload) and not truncated
    checks = {"json_object": parsed is not None, "schema": schema,
              "decision": schema and parsed[flag] == expected[flag]}
    if expected[flag]:
        checks["reference_ids"] = schema and parsed[flag] and set(parsed.get(ids_key, [])) == set(expected[ids_key])
        if task == "answerability":
            checks["user_facts"] = (schema and parsed[flag]
                                    and parsed.get("needs_user_facts") == expected["needs_user_facts"]
                                    and set(parsed.get("missing_fields", [])) == set(expected["missing_fields"]))
    return {"expected": expected, "parsed": parsed, "parse_error": error, "truncated": truncated,
            "canonical_format": bool(schema and (parsed[flag] or set(parsed) == {flag})),
            "checks": checks, "passed": all(checks.values()),
            "confusion": ("invalid" if not schema else
                          ("tp" if parsed[flag] else "fn") if expected[flag] else
                          ("fp" if parsed[flag] else "tn"))}


def percentile(values, quantile):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lo, hi = math.floor(position), math.ceil(position)
    return round(values[lo] + (values[hi] - values[lo]) * (position - lo), 3)


def summarize(cases):
    def subset(rows):
        keys = sorted({key for row in rows for key in row["checks"]})
        metrics = {}
        for key in keys:
            applicable = [row["checks"][key] for row in rows if key in row["checks"]]
            metrics[key] = {"passed": sum(applicable), "total": len(applicable), "rate": round(sum(applicable) / len(applicable), 4)}
        return {"total": len(rows), "passed": sum(row["passed"] for row in rows),
                "metrics": metrics, "confusion": {name: sum(row["confusion"] == name for row in rows) for name in ("tp", "tn", "fp", "fn", "invalid")},
                "latency_ms": {"p50": percentile([r["elapsed_ms"] for r in rows], 0.5), "p95": percentile([r["elapsed_ms"] for r in rows], 0.95)}}
    return {"all": subset(cases), "by_task": {task: subset([r for r in cases if r["task"] == task]) for task in ("answerability", "direct_evidence")}}
