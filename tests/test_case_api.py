from fastapi.testclient import TestClient
from supportpilot.api import app


def test_case_creation_and_review_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTPILOT_DB", str(tmp_path / "cases.sqlite3"))
    monkeypatch.setenv("SUPPORTPILOT_WARMUP", "0")
    monkeypatch.delenv("SUPPORTPILOT_MODEL_URL", raising=False)
    with TestClient(app) as client:
        created = client.post("/api/cases", json={"question": "비밀번호 재설정"})
        assert created.status_code == 201
        item = created.json()
        original = item["response"]["answer"]
        approved = client.post(f"/api/cases/{item['id']}/review", json={"decision": "approved", "reviewer": "상담원", "edited_answer": "확인한 답변"})
        assert approved.status_code == 200
        assert approved.json()["response"]["answer"] == original
        assert approved.json()["review"]["final_answer"] == "확인한 답변"
        assert client.get("/api/cases").json()[0]["review_status"] == "approved"
        assert client.post(f"/api/cases/{item['id']}/review", json={"decision": "rejected", "reviewer": "상담원"}).status_code == 409
        assert client.get("/api/cases/unknown").status_code == 404
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
