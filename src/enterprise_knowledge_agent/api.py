#!/usr/bin/env python3
"""FastAPI gateway in front of the deployed Foundry agent.

The agent's only tool is the knowledge base, and Foundry Agent Service executes
it server side, so the gateway is a thin HTTP client. It mirrors run_agent.py
for configuration: the project endpoint comes from .env, the agent name from
AZURE_AGENT_NAME falling back to agent_config.yaml.

The answer text keeps the agent's inline 【N:M†source】 markers unchanged; the
citation spans in the response let a client slice the answer by character index
and replace each marker with a link.

Usage:
    uv run uvicorn enterprise_knowledge_agent.api:app --reload
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Annotated, Any

import yaml
from agent_framework._sessions import AgentSession
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.getLogger("agent_framework").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[2]
AGENT_CONFIG = ROOT / "src" / "scripts" / "agent_config.yaml"

load_dotenv(ROOT / ".env")

app = FastAPI(title="Enterprise Knowledge Agent API")

# The browser sends no cookies, so credentials stay disallowed.
#
# Next.js falls back to a free port when 3000 is taken, so hardcoding one origin
# breaks the moment something else holds that port: the preflight arrives with a
# different Origin, gets a 400, and the browser reports it as a network failure.
# Any localhost port is accepted instead. Setting CORS_ORIGINS replaces this
# entirely with an explicit list, which is what a deployed frontend should use.
DEFAULT_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=None if CORS_ORIGINS else DEFAULT_ORIGIN_REGEX,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# In-memory store: conversations are lost when the process restarts.
SESSIONS: dict[str, dict[str, Any]] = {}


class Citation(BaseModel):
    url: str
    title: str | None = None
    start_index: int
    end_index: int


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation]


def _agent_name() -> str:
    name = os.environ.get("AZURE_AGENT_NAME", "")
    if name:
        return name
    if AGENT_CONFIG.is_file():
        config = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8")) or {}
        return config.get("agent_name", "")
    return ""


def get_agent() -> FoundryAgent:
    return FoundryAgent(
        project_endpoint=os.environ.get("AZURE_PROJECT_ENDPOINT", "").rstrip("/"),
        agent_name=_agent_name(),
        credential=DefaultAzureCredential(),
    )


def _collect_citations(data: Any) -> list[Citation]:
    citations: list[Citation] = []
    if isinstance(data, dict):
        if data.get("type") == "citation":
            for region in data.get("annotated_regions") or []:
                citations.append(
                    Citation(
                        url=data.get("url", ""),
                        title=data.get("title"),
                        start_index=region["start_index"],
                        end_index=region["end_index"],
                    )
                )
            return citations
        for value in data.values():
            citations.extend(_collect_citations(value))
    elif isinstance(data, list):
        for item in data:
            citations.extend(_collect_citations(item))
    return citations


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": _agent_name()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    agent: Annotated[FoundryAgent, Depends(get_agent)],
) -> ChatResponse:
    conversation_id = body.conversation_id or ""
    stored = SESSIONS.get(conversation_id) if conversation_id else None

    try:
        if stored is not None:
            session = AgentSession.from_dict(stored)
        else:
            session = await agent.create_conversation()
            conversation_id = str(uuid.uuid4())
        result = await agent.run(body.message, session=session)
    except asyncio.TimeoutError:
        logging.exception("agent request timed out")
        raise HTTPException(status_code=504, detail="The agent request timed out.")
    except Exception:
        logging.exception("agent request failed")
        raise HTTPException(status_code=502, detail="The agent request failed.")

    SESSIONS[conversation_id] = session.to_dict()
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.text,
        citations=_collect_citations(result.to_dict()),
    )
