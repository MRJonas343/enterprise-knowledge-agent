# Phase 4 API Gateway Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-19 |
| Phase | Phase 4, FastAPI Backend |
| Environment | Local process against the deployed `canadacentral` resources |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 4 exit criteria are:

> Contract and integration checks cover successful grounded answers, missing
> context, service failure, and citation preservation.

All four are covered by both a contract suite and a live integration check against
the deployed agent.

## The API

`src/enterprise_knowledge_agent/api.py`. Run with:

```bash
uv run uvicorn enterprise_knowledge_agent.api:app --reload
```

| Endpoint | Behaviour |
| --- | --- |
| `GET /api/health` | `{"status": "ok", "agent": "<name>"}`. Liveness only; performs no Azure call. |
| `POST /api/chat` | Takes `{message, conversation_id?}`, returns `{conversation_id, answer, citations}`. |

The gateway holds no retrieval logic and no prompt logic. It resolves the agent the
same way `run_agent.py` does, calls it, and maps the result onto the contract.

### The citation contract

`answer` deliberately keeps the agent's inline `【N:M†source】` markers unchanged.
Nothing is stripped, rewritten or renumbered.

`citations` supplies, per marker **occurrence**, the source URL and the exact span:

```json
{ "url": "https://…/incidents/INC-2026-002.md",
  "title": "https://…/incidents/INC-2026-002.md",
  "start_index": 614, "end_index": 626 }
```

A client can therefore slice `answer[start_index:end_index]` and replace the marker
with a link, with no lossy transformation and no guessing. This is what closes the
citation-rendering gap found in Phase 3.

`title` is passed through as-is and may duplicate the URL or be absent. The contract
does not promise a human-readable title, because the service does not provide one.

### Conversation state

Phase 4 establishes multi-turn conversations on a verified fact: **Foundry persists
conversations server-side.** The agent session's local `state` is empty and the whole
session serializes to roughly 167 characters. The gateway therefore stores a small
session dictionary keyed by a conversation id it mints, and restores it with
`AgentSession.from_dict`. No message history is stored, replayed, or summarised.

The store is an in-memory dictionary. Conversations do not survive a process restart.
This is recorded as a limitation, not a defect, and it is adequate for the MVP.

## Evidence

### 1. Contract checks

```text
tests/test_api.py::test_health                                          PASSED
tests/test_api.py::test_grounded_answer_returns_span_that_matches_the_marker PASSED
tests/test_api.py::test_unanswerable_question_is_not_an_error           PASSED
tests/test_api.py::test_agent_failure_maps_to_502                       PASSED
tests/test_api.py::test_timeout_maps_to_504                             PASSED
tests/test_api.py::test_conversation_reuse_and_new_conversation         PASSED

6 passed, 1 warning in 2.24s
```

Azure is never called in this suite. `get_agent` is overridden with a fake that
returns real `AgentResponse` objects, so the citation walk runs against the same
serialization the service produces. The one warning is a Starlette-internal
`anyio` deprecation from `TestClient`, unrelated to this code.

### 2. Integration checks against the deployed agent

Run through `TestClient` with **no** dependency override, so the real agent, the real
session and the real citations were exercised.

| Check | Observed |
| --- | --- |
| `GET /api/health` | 200, `agent` resolved to `aurora-knowledge-agent` |
| Grounded answer | 200, 2 080-character answer, 14 citations in that run |
| Citation spans | Every span sliced a marker out of the answer. E.g. `[614:626]` → `【5:0†source】` |
| URLs resolve | Citations carried real Blob URLs |
| Multi-turn | Same `conversation_id` echoed; the follow-up recalled `v2.31.0` → `v2.30.4` from the prior turn |
| Unknown `conversation_id` | A fresh conversation was minted rather than erroring |
| Missing context | 200, not an error, zero citations, refusal text returned intact |
| Real service failure | A real SDK failure (nonexistent agent name, upstream 404) mapped to **502** with body `{"detail":"The agent request failed."}` |

The failure case was driven by an actual `ChatClientException` from a live upstream
404, not by a simulated exception. The upstream detail was logged server-side and the
client body stayed generic.

## Known limitations and open items

- **Conversations are in-memory.** They do not survive a restart and do not work
  across multiple processes. Adequate for the MVP; a durable store is a later concern.
- **No authentication and no authorization.** Anyone who can reach the port can ask
  questions. Phase 9.
- **The conversation id is not an authorization boundary.** The agent framework's own
  documentation states that the service session identifier is scoped by the project,
  not by end-user identity. Phase 9 must not treat a client-supplied id as proof of
  ownership.
- **No rate limiting, no request size limits beyond Pydantic validation, and no CORS
  configuration.** Phase 5 will need CORS when the frontend runs on a different port.
- **An unknown `conversation_id` silently starts a new conversation** rather than
  reporting that the id was not found. This is deliberate and documented, but a client
  cannot distinguish "continued" from "restarted" except by comparing returned ids.
- **No tests for concurrent requests.** The session store is a plain dictionary with
  no locking. Two simultaneous first turns are fine; the same conversation driven
  concurrently is not addressed.

## What this gate does not cover

- **No latency or cost measurement.** No baseline, no percentile reporting.
- **No observability.** Failures are logged through the standard logger, with no
  traces, metrics or correlation ids. Phase 12.
- **No prompt-injection testing.** Phase 10.
- **No deployment.** The gateway runs as a local process. Containerisation, hosting
  and configuration management are later phases.
- **No UI.** Phase 5.

## Acceptance

The Phase 4 exit criteria are met. The contract is defined by Pydantic models and is
published automatically as OpenAPI at `/docs`; a contract suite covers the four
required cases without touching Azure; and a live integration run verified the same
four cases against the deployed agent, including a genuine upstream failure.

Phase 5 is unblocked. Two inputs carry forward: CORS must be configured for a
browser origin, and the client must render citations from the span data rather than
attempting to interpret `【N:M†source】` markers itself.
