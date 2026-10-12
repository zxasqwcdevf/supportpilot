from fastapi.testclient import TestClient
from supportpilot.api import app

client = TestClient(app)


def test_partial_facts():
    result = client.post("/api/questions", json={"question": "환불", "refund_facts": {"plan": "annual"}})
    assert result.status_code == 200
    assert result.json()["required_fields"] == ["payment_date", "usage_history"]


def test_invalid_facts():
    for facts in [{"plan": "invalid"}, {"payment_date": "2026-02-30"}, {"usage_history": "false"}]:
        assert client.post("/api/questions", json={"question": "환불", "refund_facts": facts}).status_code == 422
