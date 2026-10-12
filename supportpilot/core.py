import json
import re
import os
from pathlib import Path
from supportpilot.generation import generate, PipelineError, PROMPT_VERSION
from supportpilot.refund import decide
from supportpilot.retrieval import retrieve

DATA = Path(__file__).resolve().parents[1] / "data" / "policies.json"


def tokens(text: str) -> set[str]:
    # Korean substring matching is an initial baseline, not a production tokenizer.
    return set(re.findall(r"[가-힣a-z0-9]+", text.lower()))


def answer(question: str, refund_facts: dict | None = None) -> dict:
    question = question.strip()
    if not question or len(question) > 2000:
        raise ValueError("질문은 1~2000자여야 합니다.")
    documents = json.loads(DATA.read_text(encoding="utf-8"))
    hits = retrieve(question, documents)
    ranked = [(hit["score"], hit["document"]) for hit in hits]
    if not ranked:
        return {"status": "abstained", "answer": "관련 정책을 찾지 못했습니다. 상담원 확인이 필요합니다.", "citations": [], "mode": "extractive_baseline", "reason": "no_retrieval_evidence"}
    doc = ranked[0][1]
    refund = doc if doc.get("decision", {}).get("type") == "clarify_before_refund_decision" else None
    refund_intent = bool(re.search(r"환불|결제\s*취소|금액\s*반환", question))
    if refund is not None and (refund_facts is not None or (refund_intent and os.getenv("SUPPORTPILOT_MODEL_URL"))):
        return decide(refund, refund_facts)
    if os.getenv("SUPPORTPILOT_MODEL_URL"):
        # Refund eligibility requires verified facts. Do not ask the LLM to
        # infer a denial from the inverse of the full-refund condition.
        try:
            return generate(question, [item[1] for item in ranked[:3]])
        except PipelineError as exc:
            return {"status": "abstained", "answer": "모델 응답을 검증하지 못했습니다. 상담원 확인이 필요합니다.", "citations": [], "mode": "local_llm", "reason": "generation_or_validation_failed", "prompt_version": PROMPT_VERSION, "diagnostics": {"failed_stage": exc.stage, "error_type": exc.error_type, "error_code": exc.code, **exc.details}}
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            return {"status": "abstained", "answer": "모델 응답을 검증하지 못했습니다. 상담원 확인이 필요합니다.", "citations": [], "mode": "local_llm", "reason": "generation_or_validation_failed", "prompt_version": PROMPT_VERSION, "diagnostics": {"failed_stage": "pipeline", "error_code": "unclassified_failure"}}
    return {"status": "draft", "answer": doc["text"], "citations": [{"id": doc["id"], "title": doc["title"], "version": doc["version"], "quote": doc["text"]}], "mode": "extractive_baseline"}
