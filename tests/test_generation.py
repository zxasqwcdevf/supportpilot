import pytest
from unittest.mock import patch
from supportpilot.core import answer
from supportpilot.generation import validate

DOCS = [{"id": "p1", "title": "정책", "version": "1", "text": "7일 이내 환불 가능합니다."}]


def test_valid_quote():
    result = validate({"status": "draft", "answer": "7일 이내 가능합니다.", "evidence": [{"id": "p1", "quote": "7일 이내"}]}, DOCS)
    assert result["citations"][0]["id"] == "p1"


@pytest.mark.parametrize("evidence", [[{"id": "invented", "quote": "7일 이내"}], [{"id": "p1", "quote": "무조건 환불"}], []])
def test_fabricated_or_missing_evidence_rejected(evidence):
    with pytest.raises(ValueError):
        validate({"status": "draft", "answer": "환불", "evidence": evidence}, DOCS)


def test_server_failure_abstains(monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_MODEL_URL", "http://127.0.0.1:8081/v1")
    with patch("supportpilot.core.generate", side_effect=OSError("offline")):
        result = answer("비밀번호")
    assert result["status"] == "abstained"
    assert result["reason"] == "generation_or_validation_failed"


def test_unknown_question_never_calls_model(monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_MODEL_URL", "http://127.0.0.1:8081/v1")
    with patch("supportpilot.core.generate") as generate:
        assert answer("달에 서버") ["status"] == "abstained"
        generate.assert_not_called()
