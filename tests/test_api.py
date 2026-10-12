from fastapi.testclient import TestClient
from supportpilot.api import app

client = TestClient(app)


def test_health_reports_no_model():
    result = client.get("/health")
    assert result.status_code == 200
    assert result.json()["model_loaded"] is False


def test_question_returns_grounded_draft():
    result = client.post("/api/questions", json={"question": "연간 환불"})
    assert result.status_code == 200
    assert result.json()["citations"][0]["id"] == "refund-v1"


def test_whitespace_rejected():
    assert client.post("/api/questions", json={"question": "   "}).status_code == 422
