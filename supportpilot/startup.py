"""Warm the search index and model path before accepting API traffic."""
import json
import os
import time
from supportpilot.core import DATA, answer
from supportpilot.retrieval import warmup


def initialize():
    info = {"enabled": os.getenv("SUPPORTPILOT_WARMUP", "1") == "1", "ready": False}
    if not info["enabled"]:
        return info
    start = time.perf_counter()
    if os.getenv("SUPPORTPILOT_RETRIEVAL", "keyword") == "hybrid":
        warmup(json.loads(DATA.read_text(encoding="utf-8")))
    info["retrieval_ms"] = round((time.perf_counter() - start) * 1000, 3)
    start = time.perf_counter()
    if os.getenv("SUPPORTPILOT_MODEL_URL"):
        result = answer("비밀번호 재설정 링크 유효기간은?")
        if result.get("status") != "draft" or result.get("mode") != "local_llm" or result.get("diagnostics"):
            raise RuntimeError("Startup model warmup failed; inspect model server and configuration")
        info["model_path_warmed"] = True
    else:
        info["model_path_warmed"] = False
    info["model_ms"] = round((time.perf_counter() - start) * 1000, 3)
    info["ready"] = True
    return info
