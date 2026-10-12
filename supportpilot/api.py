from fastapi import FastAPI
from pydantic import BaseModel, Field, StrictBool, ConfigDict
from datetime import date
from typing import Literal
from supportpilot.core import answer
import os
import asyncio
from contextlib import asynccontextmanager
from supportpilot.startup import initialize
from supportpilot.generation import PROMPT_VERSION
from supportpilot import store
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

@asynccontextmanager
async def lifespan(app):
    app.state.warmup = await asyncio.to_thread(initialize)
    yield


app = FastAPI(title="SupportPilot", version="0.2.0", lifespan=lifespan)
STATIC = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def workspace():
    return FileResponse(STATIC / "index.html")


class RefundFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: Literal["annual", "monthly"] | None = None
    payment_date: date | None = None
    usage_history: StrictBool | None = None


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    refund_facts: RefundFacts | None = None


@app.get("/health")
def health():
    configured = bool(os.getenv("SUPPORTPILOT_MODEL_URL"))
    return {"status": "ok", "generation": "local_llm" if configured else "extractive_baseline", "model_loaded": False, "model_server_configured": configured, "prompt_version": PROMPT_VERSION, "retrieval": os.getenv("SUPPORTPILOT_RETRIEVAL", "keyword"), "warmup": getattr(app.state, "warmup", {"ready": False})}


@app.post("/api/questions")
def ask(body: Question):
    return answer(body.question, body.refund_facts.model_dump() if body.refund_facts is not None else None)


class Review(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = Field(min_length=1, max_length=100, pattern=r"\S")
    edited_answer: str | None = Field(default=None, max_length=4000)


@app.post("/api/cases", status_code=201)
def create_case(body: Question):
    response = ask(body)
    return store.create_case(body.model_dump(mode="json"), response)


@app.get("/api/cases")
def cases():
    return store.list_cases()


@app.get("/api/cases/{case_id}")
def case(case_id: str):
    try:
        return store.get_case(case_id)
    except KeyError:
        raise HTTPException(404, "Case not found")


@app.post("/api/cases/{case_id}/review")
def review(case_id: str, body: Review):
    try:
        return store.review_case(case_id, body.decision, body.reviewer, body.edited_answer)
    except KeyError:
        raise HTTPException(404, "Case not found")
    except RuntimeError:
        raise HTTPException(409, "Case already reviewed")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
