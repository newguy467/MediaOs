"""
MediaOS Safe AI router
Endpoints:
  GET  /api/ai/status   – Ollama + agent health
  POST /api/ai/chat     – talk to the safe agent
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_admin  # keep AI behind admin for safety
from app.services import ai_agent

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict[str, Any]] = []
    proposal: dict[str, Any] | None = None
    needs_confirmation: bool = False


@router.get("/status")
async def ai_status(_: None = Depends(require_admin)):
    """Return Ollama reachability and basic agent status."""
    return await ai_agent.ollama_status()


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(body: ChatRequest, _: None = Depends(require_admin)):
    """
    Send a message to the safe local agent.
    The agent is read-only by default and will only propose changes.
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]
    result = await ai_agent.chat(body.message, history)
    return ChatResponse(**result)