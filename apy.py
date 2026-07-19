"""
FastAPI-сервер: эндпоинт для официального iOS-приложения OpenClaw
и для любых других клиентов.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os

from agent import chat, chat_stream, MODEL

app = FastAPI(title="OpenClaw API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Модели запросов/ответов ───

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    model: str
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model: str
    agent: str


# ─── Эндпоинты ───

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "agent": "openclaw"}


@app.get("/v1/models")
def list_models():
    """Совместимость с OpenAI-форматом (iOS-приложение может ожидать)."""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL,
                "object": "model",
                "owned_by": "openclaw",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    """
    OpenAI-совместимый эндпоинт.
    Официальное iOS-приложение OpenClaw подключается сюда.
    """
    try:
        result = chat(req.message, req.history)
        return {
            "id": "openclaw-response",
            "object": "chat.completion",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def simple_chat(req: ChatRequest):
    """Упрощённый эндпоинт."""
    try:
        result = chat(req.message, req.history)
        return ChatResponse(response=result, model=MODEL, session_id=req.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Запуск ───

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
