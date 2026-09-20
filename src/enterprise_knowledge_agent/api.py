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
import math
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

import yaml
from agent_framework._sessions import AgentSession
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
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
    # Authorization is required so the browser may send the bearer token: a
    # cross-origin request carrying it triggers a preflight, and the browser
    # blocks the request unless the header is allowed here.
    allow_headers=["Content-Type", "Authorization"],
)

# In-memory store: conversations are lost when the process restarts. Each entry
# records the owning caller next to the serialized session, so a conversation id
# leaked to another caller cannot be used to resume it.
SESSIONS: dict[str, dict[str, Any]] = {}

# Fixed-window rate limiting, per caller, held in this process only.
#
# This is a blunt quota guard, not distributed accounting: restarting the
# process resets every counter, and two processes behind a load balancer would
# each grant the full quota. A shared store is the correct fix once the gateway
# runs scaled out.
_RATE_WINDOWS: dict[str, tuple[float, int]] = {}


class Citation(BaseModel):
    url: str
    title: str | None = None
    start_index: int
    end_index: int


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
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


def _token_map() -> dict[str, str]:
    """Parse API_TOKENS ("name:token,name:token") into {name: token}.

    Read per request rather than at import time so the value is never frozen.
    A malformed entry is skipped and the valid entries kept: one half-typed pair
    must not take the gateway down, but it also must not silently open access.
    """
    tokens: dict[str, str] = {}
    for entry in os.environ.get("API_TOKENS", "").split(","):
        name, separator, token = entry.strip().partition(":")
        if separator and name.strip() and token.strip():
            tokens[name.strip()] = token.strip()
    return tokens


def require_caller(request: Request) -> str:
    """Authenticate the request and return the caller name.

    Fails closed: an unconfigured gateway refuses to serve the request instead
    of treating "no tokens configured" as "no authentication required".
    """
    tokens = _token_map()
    if not tokens:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        )

    scheme, _, provided = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not provided:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    for name, token in tokens.items():
        # compare_digest keeps the comparison time independent of how many
        # leading characters matched, which a plain == would leak. Comparing
        # encoded bytes also avoids the TypeError that str compare_digest raises
        # for non-ASCII input.
        if secrets.compare_digest(token.encode("utf-8"), provided.encode("utf-8")):
            return name

    # Same body as a missing header: the caller learns only that they are not
    # authenticated, not whether the token was unknown or simply absent.
    raise HTTPException(
        status_code=401,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _check_rate_limit(caller: str) -> None:
    """Enforce a fixed-window request quota for one caller."""
    limit = int(os.environ.get("RATE_LIMIT_REQUESTS", "20"))
    window = float(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    now = time.monotonic()

    # Drop windows that have already closed so the table tracks recent callers
    # instead of growing with every caller the process has ever seen.
    for name in [n for n, (start, _) in _RATE_WINDOWS.items() if now - start >= window]:
        del _RATE_WINDOWS[name]

    start, count = _RATE_WINDOWS.get(caller, (now, 0))
    if now - start >= window:
        start, count = now, 0
    count += 1
    _RATE_WINDOWS[caller] = (start, count)

    if count > limit:
        retry_after = max(1, math.ceil(start + window - now))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(retry_after)},
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
    caller: Annotated[str, Depends(require_caller)],
    body: ChatRequest,
    agent: Annotated[FoundryAgent, Depends(get_agent)],
) -> ChatResponse:
    # Authentication is resolved first, so an unauthenticated request never
    # reaches the agent dependency or the rate limiter.
    _check_rate_limit(caller)

    conversation_id = body.conversation_id or ""
    stored = SESSIONS.get(conversation_id) if conversation_id else None

    if stored is not None:
        if stored["owner"] != caller:
            # 404, not 403: confirming that someone else's conversation exists
            # is itself a disclosure. A stranger gets the same answer as for an
            # id that was never issued.
            raise HTTPException(status_code=404, detail="Conversation not found.")
        session = AgentSession.from_dict(stored["session"])
    else:
        session = await agent.create_conversation()
        conversation_id = str(uuid.uuid4())

    try:
        result = await agent.run(body.message, session=session)
    except asyncio.TimeoutError:
        logging.exception("agent request timed out")
        raise HTTPException(status_code=504, detail="The agent request timed out.")
    except Exception:
        logging.exception("agent request failed")
        raise HTTPException(status_code=502, detail="The agent request failed.")

    SESSIONS[conversation_id] = {"owner": caller, "session": session.to_dict()}
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.text,
        citations=_collect_citations(result.to_dict()),
    )
