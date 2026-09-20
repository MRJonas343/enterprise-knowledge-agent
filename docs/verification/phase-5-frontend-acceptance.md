# Phase 5 Frontend Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-19 |
| Phase | Phase 5, Next.js Frontend |
| Environment | Local process against the local gateway and the deployed `canadacentral` resources |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 5 exit criteria are:

> A user can submit a question and inspect grounded citations through the API; the
> complete agent/API/UI path works without exposing secrets. This is the MVP
> completion gate.

The complete path was exercised: browser-identical HTTP requests from the frontend's
own modules reached the gateway, which reached the agent, which retrieved from the
knowledge base and returned citations that rendered into readable source links.

## What was built

`frontend/`, a separate Next.js application. It is the only MVP component not
deployed to Azure; everything before it is.

| File | Role |
| --- | --- |
| `app/page.tsx` | The entire UI, a single client component |
| `app/layout.tsx` | Minimal layout and metadata |
| `app/globals.css` | Plain CSS |
| `lib/api.ts` | Types and one `ask()` function |
| `lib/citations.ts` | The pure segment builder |
| `lib/citations.test.ts` | Ten unit tests for the pure function |

No state management library, no UI kit, no component library, no test renderer, and
no server-side data fetching. The chat is a client-side `fetch`.

Installed versions: Next 16.3.5, React 19.2.8, Vitest 5.0.1, Node 22.19.0.

The API base URL comes from `NEXT_PUBLIC_API_BASE_URL` with a hardcoded fallback of
`http://127.0.0.1:8000`, so **no environment file is required to run the frontend
locally**. Nothing secret is read, written, or bundled by the client.

## The citation rendering contract

This was the point of the phase, and the piece most likely to break silently.

The API sends `answer` with its inline `【N:M†source】` markers unchanged, plus one
citation per marker occurrence carrying a URL and a `start_index`/`end_index` pair.
`buildSegments()` sorts the citations, walks the answer with a cursor, and emits
ordered segments so the page can render readable text with numbered source links.

Verified against a live response, not a fixture:

```text
span widths observed : 12                     (a single width, as the contract states)
span [268:280]       -> 【5:1†source】          (JS slicing matches the Python offset)
span [280:292]       -> 【5:2†source】
rebuilt length       : 2605 (answer 2605)     (nothing added, nothing lost)
labels               : checkout-service.md, INC-2026-002.md, database-latency.md
```

The reassembly check is the important one: concatenating the text segments and the
original spans back together reproduces the answer **byte for byte**. The rendering
is therefore lossless.

Labels are derived from the URL's last path segment. The API's `title` duplicates the
URL and is never displayed as a label.

## Evidence

### 1. Static checks

| Command | Result |
| --- | --- |
| `npm run test` | 10 passed (1 file) in 1.24s |
| `npx tsc --noEmit` | clean, exit 0 |
| `npm run lint` | clean, exit 0 |
| `npm run build` | compiled successfully in 25.2s; `/` prerendered as static |

### 2. Live end-to-end checks

Five integration checks ran the frontend's own `ask()` and `buildSegments()` against a
live gateway and the deployed agent, with no mocking anywhere.

| Check | Observed |
| --- | --- |
| Span contract under JS semantics | 17 citations; every span exactly 12 characters; every slice matched a marker |
| Segment rendering | 19 citation segments out of 31; reassembly reproduced the 2 605-character answer exactly |
| Multi-turn | Same `conversation_id` returned; the follow-up recalled `v2.31.0` → `v2.30.4` |
| Missing context | Refusal text returned, zero citations, no error surfaced |
| CORS | A request carrying `Origin: http://localhost:3000` returned `access-control-allow-origin: http://localhost:3000` |

The CORS check is what makes the browser path real rather than assumed. It was added
to `api.py` for this phase.

## Known limitations and open items

- **No browser was driven.** The page's HTML was smoke-tested with `next start` and
  the requests were made from the frontend's own modules, but the interactive flow —
  click submit, watch the loading state, follow a citation link, press "New
  conversation" — was not exercised in a real browser. This is the one unverified step
  in the MVP path.
- **String index alignment.** Citation offsets come from a Python process and are
  applied by JavaScript. Python counts code points; JavaScript counts UTF-16 code
  units; the two diverge only on non-BMP characters. No non-BMP character exists in
  the corpus or the agent prompt, and observed spans aligned exactly, so this does not
  manifest. It would misalign if an emoji ever entered an answer.
- **Conversations remain in-memory** on the gateway and are lost on restart.
- **No authentication.** The gateway and the frontend are both unauthenticated.
  Phase 9.
- **`npx tsc --noEmit` needs a prior Next command on a fresh clone**, because the
  route types it consumes are generated into the git-ignored `.next/`.
- **No deployment.** Both the gateway and the frontend run as local processes.

## What this gate does not cover

- **No observability.** No traces, metrics or correlated logs. Phase 12.
- **No evaluation.** No groundedness scoring, no regression fixtures. Phase 11.
- **No prompt-injection or malicious-content testing.** Phase 10.
- **No retrieval optimisation.** The retrieval baseline is unchanged since Phase 2.
- **No accessibility audit, no responsive breakpoint testing, and no browser
  compatibility testing.**
- **No CI.** Nothing runs these checks automatically. Phase 13.

## Acceptance

The Phase 5 exit criteria are met, and with them the roadmap's MVP: Foundry Agent
Service, FastAPI and Next.js now provide a working end-to-end grounded user path over
three accepted gates.

## A wording inconsistency found and resolved

Recording this gate surfaced a contradiction between two of the repository's own
documents. The roadmap defines the MVP as phases 3-5. The MVP gate row in
[`AGENTS.md`](../../AGENTS.md) additionally required "MCP/tool policy, observability,
evaluation evidence, and security acceptance", which are phases 8 through 12 and
explicitly post-MVP.

Under the roadmap's definition the MVP became complete at this gate. Under the gate
row's wording it could not be claimed until most of the post-MVP phases were finished.
Both could not be true.

**Resolved by the project owner: the MVP is phases 3-5.** The gate row in `AGENTS.md`
was corrected to match the roadmap, so the MVP is complete with this gate.

The correction is recorded rather than applied silently, because changing what a
milestone means would otherwise make every earlier acceptance record unreadable. No
phase evidence changed; only the wording of the milestone.

