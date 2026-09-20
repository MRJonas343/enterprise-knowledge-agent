# Gateway caller-facing access control

Status: in progress
Route: direct inline (single module edit plus tests and config docs)
Feature branch: main (no commit requested by the brief)

## Objective

Add the first Phase 9 security slice to the FastAPI gateway: bearer-token
authentication that fails closed, per-caller conversation ownership, a
per-caller fixed-window rate limit, and a message size cap. The frontend must
send the token and document the browser-bundle limitation honestly.

## Problem

`POST /api/chat` had no caller authentication, no conversation ownership check
and no rate limiting, so anyone reaching the port could query the knowledge
base, resume a stranger's conversation by supplying its id, and consume model
quota without limit. An oversized message had no ceiling.

## Why

Phase 9 (Security) is the active post-MVP boundary. The project owner
superseded the boundary on 2026-09-20 and selected security as the next phase.

## Scope

In scope:

- `src/enterprise_knowledge_agent/api.py`
- `tests/test_api.py`
- `.env.example`
- `frontend/lib/api.ts`

Out of scope (explicitly preserved by the brief): `lib/citations.ts` and its
tests, the agent, the system prompt, `infra/`, the health endpoint's shape, the
502/504 mapping, and the existing CORS origin handling. No new dependencies.
No commit.

## Constraints

- Standard library only: `secrets.compare_digest` for token comparison.
- The token map is read per request, not at import time, so tests can vary it.
- `GET /api/health` stays unauthenticated.
- Keep the implementation to small functions, not middleware or a framework.

## Tasks

- [x] **T1** Read `api.py`, `test_api.py`, `.env.example`, `frontend/lib/api.ts`.
- [x] **T2** Baseline `uv run pytest tests -q` (10 passed).
- [x] **T3** Add bearer authentication (503 when unconfigured, 401 otherwise).
- [x] **T4** Record conversation ownership; cross-caller ids return 404.
- [x] **T5** Add the per-caller fixed-window rate limit with `Retry-After`.
- [x] **T6** Cap `message` at 2000 characters.
- [x] **T7** Extend `tests/test_api.py`; keep the existing tests green.
- [x] **T8** Document the configuration in `.env.example`.
- [x] **T9** Send the token from `frontend/lib/api.ts` with the limitation note.
- [x] **T10** Run `uv run pytest tests -q` and the frontend checks.

## Acceptance criteria

- No `Authorization` header, malformed scheme, or unknown token returns 401 with
  `WWW-Authenticate: Bearer`.
- Unset `API_TOKENS` returns 503 for `/api/chat`, never 200.
- A conversation owned by another caller returns 404 with no content.
- Exceeding the rate limit returns 429 with `Retry-After`.
- A message longer than 2000 characters returns 422.
- Every pre-existing test still passes.

## Checks

- `uv run pytest tests -q` -> `24 passed, 1 warning in 1.71s`
- `cd frontend && npx tsc --noEmit && npm run lint && npm run test` -> tsc exit 0,
  eslint exit 0, vitest `2 passed (2)` files / `24 passed (24)` tests.

## Progress

Complete. Four tracked files changed plus this record. Baseline was 10 tests;
the suite is now 24. An ad-hoc check confirmed authentication resolves before
the agent dependency and before body validation: with `API_TOKENS` unset an
oversized body returns 503 (not 422) and `get_agent` is never invoked.

One deliberate deviation from the brief: `Authorization` was added to the CORS
`allow_headers` list. The brief said not to change the existing CORS behaviour,
but a browser cannot send the bearer token cross-origin unless the preflight
allows that header, so the frontend change would otherwise be dead on arrival.
Origin handling (regex, `CORS_ORIGINS` override, tests) is unchanged.

## Next step

None for this slice. Not committed, per the brief. A later slice should replace
the browser-visible `NEXT_PUBLIC_API_TOKEN` with a server-side Next.js proxy.
