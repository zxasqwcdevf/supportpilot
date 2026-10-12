"""Run in WSL: python -m uvicorn scripts.model_server:app --port 8081."""
import os
import threading
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = os.getenv("SUPPORTPILOT_MODEL", "Qwen/Qwen3-4B-Instruct-2507")
lock = threading.Lock()
tokenizer = None
model = None


@asynccontextmanager
async def lifespan(app):
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map={"": 0})
    model.eval()
    yield


app = FastAPI(lifespan=lifespan)


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(max_length=20000)


class Completion(BaseModel):
    model: str
    messages: list[Message] = Field(min_length=1, max_length=10)
    max_tokens: int = Field(default=512, ge=1, le=512)
    temperature: float = Field(default=0, ge=0, le=0)


@app.get("/health")
def health():
    return {"model": MODEL, "loaded": model is not None}


@app.post("/v1/chat/completions")
def completion(body: Completion):
    from fastapi import HTTPException
    if body.model != MODEL:
        raise HTTPException(400, "Requested model does not match loaded model")
    with lock, torch.inference_mode():
        text = tokenizer.apply_chat_template([m.model_dump() for m in body.messages], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
        length = inputs["input_ids"].shape[1]
        if length + body.max_tokens > 4096:
            raise HTTPException(413, "Input plus output exceeds 4096 tokens")
        output = model.generate(**inputs, max_new_tokens=body.max_tokens, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        content = tokenizer.decode(output[0, length:], skip_special_tokens=True)
    generated = output[0, length:]
    finish_reason = "length" if len(generated) >= body.max_tokens and (len(generated) == 0 or generated[-1].item() != tokenizer.eos_token_id) else "stop"
    return {"model": MODEL, "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}], "usage": {"prompt_tokens": length, "completion_tokens": len(generated)}}
