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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

import yaml
from agent_framework._sessions import AgentSession
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)
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
    # `url` is the canonical Blob URL: the identity of the source. It is never a
    # credential. `source_url` is a short-lived, read-only SAS URL a client can
    # actually open, or None when it could not be minted.
    url: str
    source_url: str | None = None
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


# Codes the service uses when a Responsible AI policy blocks a turn. The two
# spellings are the same refusal; both are observed in the wild.
_CONTENT_FILTER_CODES = frozenset({"content_filter", "content_policy_violation"})

# A refusal is a client-error response. A code that shows up on a 5xx or a 429
# is a service failure wearing the same code, and must not be reported as a 400.
_CONTENT_FILTER_STATUSES = frozenset({400, 403})

# Azure marks a policy block in the inner error as well as in the outer code.
_RESPONSIBLE_AI_INNER_CODE = "ResponsibleAIPolicyViolation"

# The chain is one or two links in practice; a hard bound makes a cycle
# impossible even if the visited-id guard below were ever wrong.
_MAX_EXCEPTION_CHAIN = 10


def _safe_getattr(obj: object, name: str) -> Any:
    """Read an attribute, returning None if the read fails for any reason.

    getattr with a default only swallows AttributeError. This runs while
    classifying a failure, so a property that raises anything else must not be
    able to turn the 400 this exists to produce into a 500.
    """
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def _is_content_filter_error(exc: BaseException) -> bool:
    """Return True when exc is a content-safety block, not a real failure.

    A blocked turn arrives as an ordinary HTTP 400 whose body carries a
    content-filter code, so the client raises the same bad-request type it uses
    for every other 4xx. Reporting that as a 502 would tell the caller the
    gateway is broken when the caller's own message is what was refused. The
    same code on a 5xx or a 429 is a service failure, not a refusal, and is left
    alone.

    The exception shape depends on which client raised it, and the real one may
    be wrapped by another exception, so the __cause__/__context__ chain is
    inspected. Every read is defensive on purpose: this runs while classifying a
    failure, and raising here would turn the 400 this exists to produce back
    into a 500.
    """
    seen: set[int] = set()
    current: BaseException | None = exc

    for _ in range(_MAX_EXCEPTION_CHAIN):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))

        # The framework defines ContentFilterException types but raises none of
        # them today. Matching by name catches them without importing them.
        if type(current).__name__.endswith("ContentFilterException"):
            return True

        # The openai SDK shape: the code sits directly on the exception.
        status = _safe_getattr(current, "status_code")
        # A code alone is not enough. A 429 or a 500 whose body happens to carry
        # a content-filter code is a service failure; reporting it as a 400 would
        # hide breakage. Accept the code only when the status is absent, or is
        # the client-error status a refusal actually uses.
        status_is_refusal = status is None or status in _CONTENT_FILTER_STATUSES
        code = _safe_getattr(current, "code")
        if status_is_refusal and isinstance(code, str) and code in _CONTENT_FILTER_CODES:
            return True

        # The azure-core shape: the parsed ODataV4Format hangs off `error`.
        error = _safe_getattr(current, "error")
        if error is not None:
            error_code = _safe_getattr(error, "code")
            if status_is_refusal and isinstance(error_code, str) and error_code in _CONTENT_FILTER_CODES:
                return True
            inner = _safe_getattr(error, "innererror")
            # azure-core parses innererror into a plain dict; tolerate an object
            # too, in case another client hands the same shape back as a model.
            inner_code = inner.get("code") if isinstance(inner, dict) else _safe_getattr(inner, "code")
            if status_is_refusal and isinstance(inner_code, str) and inner_code == _RESPONSIBLE_AI_INNER_CODE:
                return True

        # Last resort, and deliberately narrow: a bare 400 or 403 is far too
        # common to mean "blocked", so the documented policy wording must appear
        # as well. str() on an exception is not guaranteed to succeed.
        if status in (400, 403):
            try:
                text = str(current).lower()
            except Exception:
                text = ""
            if "content management policy" in text:
                return True

        current = _safe_getattr(current, "__cause__") or _safe_getattr(current, "__context__")

    return False


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


# Citation source links are short-lived: they are links inside an answer, not
# downloads to keep. Five minutes is enough for a reader to click one.
SAS_LIFETIME = timedelta(minutes=5)

# Backdating the SAS start absorbs clock skew between the gateway and Blob.
SAS_START_SKEW = timedelta(seconds=60)

# get_user_delegation_key is a network round trip, and the gateway talks to one
# storage account, so one key is cached and reused until shortly before expiry.
# Without this a chat response would pay that round trip once per citation.
DELEGATION_KEY_LIFETIME = timedelta(hours=1)
DELEGATION_KEY_REFRESH_MARGIN = timedelta(seconds=60)

_delegation_key: UserDelegationKey | None = None
_delegation_key_expiry: datetime | None = None


def corpus_blob_target(url: str) -> tuple[str, str] | None:
    """Return (container, blob_path) if url is a corpus Blob URL, else None.

    This is a security control, not a convenience: whatever this returns is what
    the gateway proceeds to sign. Anything outside the configured storage account
    and knowledge container is refused, so a SAS is never minted for a URL the
    corpus does not own.

    The account and container are read per call, like the token map, so tests and
    a redeployed gateway can vary them without reimporting this module.
    """
    account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "").strip().lower()
    container = os.environ.get("AZURE_KNOWLEDGE_CONTAINER", "enterprise-knowledge").strip()
    if not account or not container:
        return None

    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    # parsed.hostname is lowercased and excludes any port. A lookalike such as
    # "…blob.core.windows.net.evil.example" has a different hostname and fails
    # here, as does a different account or a non-https scheme.
    if parsed.scheme != "https":
        return None
    if (parsed.hostname or "").lower() != f"{account}.blob.core.windows.net":
        return None

    # A canonical citation URL carries no query or fragment; one that does is not
    # the bare identity we sign against.
    if parsed.query or parsed.fragment:
        return None

    # Blob URLs are /<container>/<blob path>.
    if not parsed.path.startswith("/"):
        return None
    container_name, separator, blob_path = parsed.path[1:].partition("/")
    if not separator or container_name != container or not blob_path:
        return None

    # Refuse dot segments and backslashes: the blob path must read as a literal
    # path under the container, never as traversal out of it.
    if "\\" in blob_path or any(part in ("", ".", "..") for part in blob_path.split("/")):
        return None

    return container_name, blob_path


def _fetch_user_delegation_key() -> UserDelegationKey:
    """Ask Blob for a user-delegation key. This is the only network call here."""
    account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=DefaultAzureCredential(),
    )
    now = datetime.now(timezone.utc)
    return service.get_user_delegation_key(
        key_start_time=now,
        key_expiry_time=now + DELEGATION_KEY_LIFETIME,
    )


def _user_delegation_key() -> UserDelegationKey:
    """Return the cached delegation key, refetching shortly before it expires."""
    global _delegation_key, _delegation_key_expiry
    now = datetime.now(timezone.utc)
    if (
        _delegation_key is not None
        and _delegation_key_expiry is not None
        and now + DELEGATION_KEY_REFRESH_MARGIN < _delegation_key_expiry
    ):
        return _delegation_key
    key = _fetch_user_delegation_key()
    _delegation_key = key
    _delegation_key_expiry = key.signed_expiry
    return key


def _mint_source_url(url: str) -> str | None:
    """Return a short-lived read-only SAS URL for a corpus citation, or None.

    Fail soft: a citation whose link cannot be minted is still returned, with
    source_url None. An answer without a working link is degraded; an answer
    replaced by a 500 because a secondary concern failed is broken.
    """
    target = corpus_blob_target(url)
    if target is None:
        return None
    container, blob_path = target

    try:
        account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
        now = datetime.now(timezone.utc)
        sas = generate_blob_sas(
            account_name=account,
            container_name=container,
            blob_name=blob_path,
            user_delegation_key=_user_delegation_key(),
            permission=BlobSasPermissions(read=True),
            start=now - SAS_START_SKEW,
            expiry=now + SAS_LIFETIME,
        )
    except Exception:
        logging.exception("could not mint a source link for %s", url)
        return None

    return f"{url}?{sas}"


def _collect_citations(data: Any) -> list[Citation]:
    citations: list[Citation] = []
    if isinstance(data, dict):
        if data.get("type") == "citation":
            for region in data.get("annotated_regions") or []:
                url = data.get("url", "")
                citations.append(
                    Citation(
                        url=url,
                        source_url=_mint_source_url(url),
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
    except Exception as exc:
        if _is_content_filter_error(exc):
            # 400, not 502: the caller's own input caused this and retrying the
            # same message will not help. Log the caller, never the message —
            # the blocked text is exactly what must not end up in a log.
            logging.warning("content filter blocked a request from %s", caller)
            raise HTTPException(
                status_code=400,
                detail="Blocked by a content safety policy. Rephrase the question and try again.",
            )
        logging.exception("agent request failed")
        raise HTTPException(status_code=502, detail="The agent request failed.")

    SESSIONS[conversation_id] = {"owner": caller, "session": session.to_dict()}
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.text,
        citations=_collect_citations(result.to_dict()),
    )
