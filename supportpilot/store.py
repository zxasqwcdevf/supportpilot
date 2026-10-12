"""SQLite case history and immutable reviewer decisions for local demos."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def connect():
    path = Path(os.getenv("SUPPORTPILOT_DB", str(Path(__file__).resolve().parents[1] / "runtime/supportpilot.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, request_json TEXT NOT NULL,
            response_json TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            reviewer TEXT NOT NULL, decision TEXT NOT NULL, final_answer TEXT NOT NULL,
            FOREIGN KEY(case_id) REFERENCES cases(id));
    ''')
    return db


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def create_case(request, response):
    case_id = str(uuid.uuid4())
    db = connect()
    try:
        with db:
            db.execute("INSERT INTO cases(id,created_at,request_json,response_json) VALUES(?,?,?,?)", (case_id, timestamp(), json.dumps(request, ensure_ascii=False, default=str), json.dumps(response, ensure_ascii=False)))
    finally:
        db.close()
    return get_case(case_id)


def get_case(case_id):
    db = connect()
    try:
        row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError("Case not found")
        review = db.execute("SELECT * FROM reviews WHERE case_id=?", (case_id,)).fetchone()
        return {"id": row["id"], "created_at": row["created_at"], "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"]), "review_status": row["review_status"], "review": dict(review) if review else None}
    finally:
        db.close()


def list_cases(limit=50):
    db = connect()
    try:
        rows = db.execute("SELECT id,created_at,request_json,review_status FROM cases ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r["id"], "created_at": r["created_at"], "question": json.loads(r["request_json"])["question"], "review_status": r["review_status"]} for r in rows]
    finally:
        db.close()


def review_case(case_id, decision, reviewer, edited_answer=None):
    if decision not in {"approved", "rejected"} or not reviewer.strip():
        raise ValueError("Invalid review")
    db = connect()
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if row is None:
                raise KeyError("Case not found")
            if row["review_status"] != "pending":
                raise RuntimeError("Case already reviewed")
            result = json.loads(row["response_json"])
            if decision == "approved" and result["status"] in {"abstained", "requires_review"} and not (edited_answer and edited_answer.strip() and edited_answer.strip() != result["answer"].strip()):
                raise ValueError("Provide a reviewed answer before approving a withheld response")
            final = (edited_answer.strip() if edited_answer and edited_answer.strip() else result["answer"]) if decision == "approved" else ""
            db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), case_id, timestamp(), reviewer.strip(), decision, final))
            db.execute("UPDATE cases SET review_status=? WHERE id=?", (decision, case_id))
    finally:
        db.close()
    return get_case(case_id)
