"""Tests for the FastAPI gateway.

Azure is never called: `get_agent` is overridden with a fake that returns real
agent-framework response objects, so the citation walk is exercised against the
same serialization the service produces.
"""

from __future__ import annotations

import asyncio

import pytest
from agent_framework import AgentResponse, Content, Message
from agent_framework._sessions import AgentSession
from fastapi.testclient import TestClient

from enterprise_knowledge_agent import api

MARKER = "【5:1†source】"

ALICE = "tok_alice"
BOB = "tok_bob"


class FakeAgent:
    def __init__(self, *, answer: str = "ok", spans: list[tuple[str, str | None, int, int]] | None = None, error: Exception | None = None):
        self.answer = answer
        self.spans = spans or []
        self.error = error
        self.created = 0
        self.sessions: list[AgentSession] = []

    async def create_conversation(self) -> AgentSession:
        self.created += 1
        return AgentSession(session_id=f"session-{self.created}", service_session_id=f"service-{self.created}")

    async def run(self, message: str, *, session: AgentSession | None = None) -> AgentResponse:
        if session is not None:
            self.sessions.append(session)
        if self.error is not None:
            raise self.error
        annotations = [
            {
                "type": "citation",
                "title": title,
                "url": url,
                "annotated_regions": [{"type": "text_span", "start_index": start, "end_index": end}],
            }
            for url, title, start, end in self.spans
        ]
        content = Content.from_text(self.answer, annotations=annotations)
        message_obj = Message(role="assistant", contents=[content])
        return AgentResponse(messages=[message_obj])


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # The token map and the rate-limit settings are read per request, so setting
    # them here is enough; monkeypatch restores the real environment afterwards.
    monkeypatch.setenv("API_TOKENS", f"alice:{ALICE},bob:{BOB}")
    api.SESSIONS.clear()
    api._RATE_WINDOWS.clear()
    yield
    api.SESSIONS.clear()
    api._RATE_WINDOWS.clear()
    api.app.dependency_overrides.clear()


def _client(fake: FakeAgent, token: str | None = ALICE) -> TestClient:
    api.app.dependency_overrides[api.get_agent] = lambda: fake
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return TestClient(api.app, headers=headers)


def test_health(monkeypatch):
    monkeypatch.setenv("AZURE_AGENT_NAME", "test-agent")
    response = _client(FakeAgent()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "agent": "test-agent"}


def test_grounded_answer_returns_span_that_matches_the_marker():
    answer = f"Checkout latency is documented in the service guide {MARKER} and the runbook."
    start = answer.index(MARKER)
    end = start + len(MARKER)
    fake = FakeAgent(answer=answer, spans=[("https://example/checkout-service.md", None, start, end)])

    response = _client(fake).post("/api/chat", json={"message": "checkout latency?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == answer
    assert len(body["citations"]) == 1
    first = body["citations"][0]
    assert first["url"] == "https://example/checkout-service.md"
    assert first["title"] is None
    assert body["answer"][first["start_index"]:first["end_index"]] == MARKER


def test_unanswerable_question_is_not_an_error():
    fake = FakeAgent(answer="I could not find enough information in the available company knowledge to answer this reliably.")
    response = _client(fake).post("/api/chat", json={"message": "what is the airspeed of a swallow?"})

    assert response.status_code == 200
    assert response.json()["citations"] == []


def test_agent_failure_maps_to_502():
    response = _client(FakeAgent(error=RuntimeError("boom"))).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 502


def test_timeout_maps_to_504():
    response = _client(FakeAgent(error=asyncio.TimeoutError())).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 504


def test_conversation_reuse_and_new_conversation():
    fake = FakeAgent()
    client = _client(fake)

    first = client.post("/api/chat", json={"message": "one"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id
    assert fake.created == 1

    second = client.post("/api/chat", json={"message": "two", "conversation_id": conversation_id})
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert fake.created == 1
    assert len(fake.sessions) == 2
    assert fake.sessions[0].service_session_id == fake.sessions[1].service_session_id

    third = client.post("/api/chat", json={"message": "three"})
    assert third.status_code == 200
    assert third.json()["conversation_id"] != conversation_id
    assert fake.created == 2


def test_cors_allows_the_frontend_origin():
    response = _client(FakeAgent()).get(
        "/api/health", headers={"Origin": "http://localhost:3000"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_allows_the_port_next_falls_back_to():
    # Next.js takes another port when 3000 is busy. The preflight then carries a
    # different Origin, and a hardcoded allowlist rejects it as a 400.
    response = _client(FakeAgent()).get(
        "/api/health", headers={"Origin": "http://localhost:3001"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"


def test_cors_preflight_succeeds_for_a_fallback_port():
    response = _client(FakeAgent()).options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200


def test_cors_rejects_an_unknown_origin():
    response = _client(FakeAgent()).get(
        "/api/health", headers={"Origin": "http://not-our-frontend.example"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_the_authorization_header():
    # The browser preflights a cross-origin request carrying the bearer token;
    # if the header is not allowed here the browser never sends the request.
    response = _client(FakeAgent()).options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


# --- Authentication ---------------------------------------------------------


def test_missing_authorization_header_is_401():
    response = _client(FakeAgent(), token=None).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_malformed_authorization_scheme_is_401():
    response = _client(FakeAgent()).post(
        "/api/chat", json={"message": "hi"}, headers={"Authorization": "Basic xyz"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_token_is_401():
    response = _client(FakeAgent(), token="tok_not_issued").post(
        "/api/chat", json={"message": "hi"}
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_valid_token_is_200():
    response = _client(FakeAgent()).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 200


def test_unconfigured_tokens_fail_closed_with_503(monkeypatch):
    # The most important behaviour: a missing configuration must never fall
    # through to serving the request.
    monkeypatch.delenv("API_TOKENS", raising=False)
    response = _client(FakeAgent()).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured."}


def test_empty_tokens_fail_closed_with_503(monkeypatch):
    monkeypatch.setenv("API_TOKENS", "   ")
    response = _client(FakeAgent()).post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503


def test_malformed_token_entries_are_skipped(monkeypatch):
    monkeypatch.setenv("API_TOKENS", "alice:tok_alice,not-a-pair,bob:tok_bob,:")

    assert _client(FakeAgent(), token=ALICE).post("/api/chat", json={"message": "hi"}).status_code == 200
    assert _client(FakeAgent(), token=BOB).post("/api/chat", json={"message": "hi"}).status_code == 200
    assert _client(FakeAgent(), token="not-a-pair").post("/api/chat", json={"message": "hi"}).status_code == 401


# --- Conversation ownership -------------------------------------------------


def test_conversation_owned_by_another_caller_is_404():
    fake = FakeAgent()
    alice = _client(fake, token=ALICE)
    bob = _client(fake, token=BOB)

    created = alice.post("/api/chat", json={"message": "one"})
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    response = bob.post("/api/chat", json={"message": "two", "conversation_id": conversation_id})

    assert response.status_code == 404
    # The refusal must not disclose the conversation or its contents.
    assert conversation_id not in response.text
    assert "answer" not in response.text
    assert fake.created == 1


def test_caller_can_continue_their_own_conversation():
    fake = FakeAgent()
    alice = _client(fake, token=ALICE)

    created = alice.post("/api/chat", json={"message": "one"})
    conversation_id = created.json()["conversation_id"]

    second = alice.post("/api/chat", json={"message": "two", "conversation_id": conversation_id})

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


# --- Rate limiting ----------------------------------------------------------


def test_exceeding_the_rate_limit_is_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    client = _client(FakeAgent())

    assert client.post("/api/chat", json={"message": "one"}).status_code == 200
    second = client.post("/api/chat", json={"message": "two"})

    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1


def test_rate_limit_is_per_caller(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    fake = FakeAgent()
    alice = _client(fake, token=ALICE)
    bob = _client(fake, token=BOB)

    assert alice.post("/api/chat", json={"message": "one"}).status_code == 200
    assert alice.post("/api/chat", json={"message": "two"}).status_code == 429
    # A different caller has their own window.
    assert bob.post("/api/chat", json={"message": "three"}).status_code == 200


def test_expired_rate_window_is_pruned(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "5")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "0")
    alice = _client(FakeAgent(), token=ALICE)
    bob = _client(FakeAgent(), token=BOB)

    assert alice.post("/api/chat", json={"message": "one"}).status_code == 200
    assert bob.post("/api/chat", json={"message": "two"}).status_code == 200
    assert alice.post("/api/chat", json={"message": "three"}).status_code == 200

    # A zero-length window closes immediately, so each request drops the closed
    # windows instead of accumulating one entry per caller forever.
    assert list(api._RATE_WINDOWS) == ["alice"]


# --- Request size -----------------------------------------------------------


def test_message_over_two_thousand_characters_is_422():
    response = _client(FakeAgent()).post("/api/chat", json={"message": "x" * 2001})
    assert response.status_code == 422
