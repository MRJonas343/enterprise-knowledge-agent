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
def _isolate():
    api.SESSIONS.clear()
    yield
    api.SESSIONS.clear()
    api.app.dependency_overrides.clear()


def _client(fake: FakeAgent) -> TestClient:
    api.app.dependency_overrides[api.get_agent] = lambda: fake
    return TestClient(api.app)


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
