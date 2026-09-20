# Phase 3 Agent Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-19 |
| Phase | Phase 3, Foundry Agent MVP |
| Environment | `canadacentral`, single resource group `rg-knowledge-agent-344` |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 3 exit criteria are:

> Agent behavior is verified against the accepted retrieval path, with service/API
> versions, citation preservation, and failure behavior documented.

This record covers all four: the agent runs against the accepted Phase 2 retrieval
path, the deployed versions are pinned below, citation preservation was inspected at
the object level, and four failure modes were exercised and their behaviour recorded.

## Deployed agent

| Field | Value |
| --- | --- |
| Agent name | `aurora-knowledge-agent` |
| Agent version | `1`, created `2026-09-19T23:25:52Z` |
| Model | `gpt-5.4-mini`, version `2026-03-17` |
| Tool | `knowledge_base_retrieve` over MCP, server label `knowledge-base` |
| Tool approval | `require_approval = never` |
| Connection | `RemoteTool`, `authType ProjectManagedIdentity`, audience `https://search.azure.com/` |
| MCP endpoint | `{search}/knowledgebases/enterprise-knowledge-base/mcp?api-version=2026-08-01-preview` |

The agent's only tool is the knowledge base. The connection is referenced by its ARM
ID, not its name; passing the name fails at runtime with
`Connection resolution failed`. The agent name and system prompt come from
`src/scripts/agent_config.yaml`, which `deploy_agent.py` and `run_agent.py` both read,
so the published and the invoked agent cannot drift.

## Service and API versions

| Component | Version |
| --- | --- |
| `agent-framework` | 1.19.0 |
| `azure-ai-projects` | 2.7.0 |
| `azure-search-documents` | 12.1.0b2 (preview, required for the knowledge base surface) |
| `azure-identity` | 1.25.3 |
| `mcp` | 1.30.0 |
| Knowledge base MCP API | `2026-08-01-preview` |
| ARM project connections API | `2025-10-01-preview` |

## Evidence

### 1. Citation preservation

Citations are preserved as structured objects, not as text the model happened to
write. The response message carries a `text` content block with **25 `citation`
annotations**, shaped:

```json
{
  "type": "citation",
  "title": "https://knowledgeagent343.blob.core.windows.net/enterprise-knowledge/architecture/checkout-service.md",
  "url": "https://knowledgeagent343.blob.core.windows.net/enterprise-knowledge/architecture/checkout-service.md",
  "annotated_regions": [{ "type": "text_span", "start_index": 317, "end_index": 329 }]
}
```

The annotations resolve to real Blob URLs, and each `annotated_regions` span is
exactly 12 characters wide, covering one inline marker in the answer text. At
`start_index` 317 the underlying text is `【5:1†source】`, confirming the span marks
the citation marker itself. The answer therefore carries source attribution in two
forms: readable inline markers, and machine-resolvable URL plus span.

**Documented limitations of the citation object.** Three fields that exist in the
`Annotation` schema are absent in practice: `file_id`, `tool_name` and `snippet` are
not populated. `title` duplicates `url` rather than being a human-readable document
title. A consumer therefore gets the source URL and the exact span, but no title and
no snippet.

**Client limitation.** `src/enterprise_knowledge_agent/run_agent.py` prints only
`result.text`. The inline `【5:N†source】` markers are visible but nothing resolves
them to URLs, so the terminal client shows markers a reader cannot follow. This is a
gap in the client, not in the agent, and it is a Phase 4 concern.

### 2. The knowledge base was actually used

The assistant message contains, in order, three content blocks:

```text
mcp_server_tool_call    tool=knowledge_base_retrieve  server=knowledge-base
mcp_server_tool_result  (22 670 characters)
text                    2 823 characters, 25 citation annotations
```

The tool call and its result are in the response itself, which is direct evidence
that the answer was built from retrieval rather than from model memory.

The agent passed the user's question verbatim as a single `query_variants` entry
rather than decomposing it. That is consistent with the knowledge base being
configured at low retrieval reasoning effort, and it means query planning is a
tunable surface rather than something the agent currently exercises.

### 3. Retrieval breadth

Across recorded runs the retrieval step returned **five or six distinct documents**,
eight chunks in the first recorded run. The set varies by run; documents observed
include `checkout-service.md`, `payment-service.md`, `system-overview.md`,
`database-latency.md`, `INC-2026-001.md`, `INC-2026-002.md` and `INC-2026-003.md`.

The answer cited between three and five of them. Citing fewer documents than were
retrieved is expected and correct: retrieval is recall-oriented and the model selects
what the answer needs.

### 4. Conversation state

Three turns were run in one session. Turn 2 ("And which one of those would you check
first?") resolved "those" against turn 1 without asking for clarification, and turn 3
recalled the rollback version named in turn 1. The citation prefixes advanced
`5:` → `9:` → `13:` across turns, consistent with message accumulation in the session.

Conversation state therefore works within a session. Durable, cross-session
conversation history was not tested and is not claimed.

### 5. Failure behavior

Four failure modes were exercised.

**a. Question with no corpus coverage.** Asked about a parental leave policy, the
agent called the tool, the tool returned empty content, and the agent refused:

> I could not find enough information in the available company knowledge to answer
> this reliably.

Zero citations were attached. The agent attempted retrieval, observed nothing, and
declined rather than inventing. This is the intended behaviour and it was reproduced
in the Phase 2 adversarial probes.

**b. Missing knowledge base.** Calling `tools/call` against a knowledge base name
that does not exist returns **HTTP 200** carrying a JSON-RPC application error:

```json
{ "result": { "content": [ { "type": "text", "text":
  "An error occurred invoking 'knowledge_base_retrieve': NotFound Message-
   {\"Message\":\"No Knowledge Base with the name 'does-not-exist-kb' was found
   in service 'knowledge-agent-343-search'.\", ...} RequestId: ..." } ],
  "isError": true }, "id": 1, "jsonrpc": "2.0" }
```

**This is the single most important failure-semantics finding in this record: HTTP
status is not the failure signal in MCP.** A client that checks only the HTTP status
will treat a missing knowledge base as success. The `isError` flag and the
`result.content[].text` payload carry the failure.

**c. Authentication failure.** `tools/call` without a bearer token returns HTTP 401
with a `WWW-Authenticate` challenge naming the tenant authorization endpoint and
`resource="https://search.azure.com"`. (The tenant identifier is redacted here.)

**d. `tools/list` is not an existence check.** `tools/list` returns HTTP 200 with a
valid `knowledge_base_retrieve` tool definition **even for a knowledge base that does
not exist**. Probing with `tools/list` cannot distinguish a real knowledge base from
a missing one; only `tools/call` reveals it.

**e. Timeout — partially covered.** Only a client-side timeout was exercised: a
2 second `asyncio.wait_for` around the agent run, which surfaced cleanly as
`TimeoutError` rather than a crash. The knowledge base's own
`max_runtime_in_seconds = 45` limit was **not** forced end to end, and the behaviour
when the service itself exceeds that budget is not recorded here.

## Non-determinism

Agentic retrieval is not deterministic, and answers vary run to run in both wording
and content. Three claims appeared in every recorded run:

- the synchronous call from checkout-api to payment-service with a 2 second timeout
  and no circuit breaker;
- the `settlements` query with no supporting index;
- PgBouncer pool exhaustion and the rollback from v2.31.0.

Other claims varied. The 80% alert threshold appeared in two of three dedicated runs,
the p95 latency figure in two of three, and the 6% error rate in one of three. The
cited-document count ranged from three to five.

This is a property of the system, not a defect, but it means a single observed run is
weak evidence. See the erratum in
[the Phase 2 record](phase-2-retrieval-acceptance.md#erratum-2026-09-19), where
exactly this produced an overstated claim.

## Known limitations and open items

- `run_agent.py` does not resolve citation markers to URLs, so its output is not
  independently verifiable by a reader. A Phase 4 concern.
- The citation `title` field is not human-readable, and `file_id`, `tool_name` and
  `snippet` are unpopulated.
- Service-side timeout behaviour is not covered.
- `require_approval` is `never`, so the agent calls the knowledge base without human
  approval. Acceptable for read-only retrieval; worth revisiting when write-capable
  tools arrive.
- The agent's tool surface is read-only. Nothing in this record exercises a
  state-changing operation.

## What this gate does not cover

- **No automated tests.** Every check in this record was executed by a human-operated
  script and read from its output. There is no test suite, and nothing here is
  regression-protected.
- **No evaluation, latency or cost measurement.** Groundedness scoring, retrieval
  quality scoring, token accounting and latency distribution belong to Phase 11 and
  are absent.
- **No observability.** The evidence came from response payloads and direct HTTP
  probes, not from traces, metrics or correlated logs. Phase 12.
- **No prompt-injection or malicious-content testing.** Phase 10. Nothing here
  establishes that a poisoned document cannot influence the agent.
- **No multi-user, permission or identity boundary testing.** Phase 9.
- **No cross-session conversation durability.**

## Acceptance

The Phase 3 exit criteria are met: agent behaviour was verified against the accepted
Phase 2 retrieval path, versions are pinned, citation preservation was inspected at
the object level, and failure behaviour is documented for four modes.

The limitations above are recorded rather than waived. Phase 4 is unblocked, and the
citation-rendering gap in `run_agent.py` is carried forward as a concrete input to
the API contract rather than left as a client-side oversight.
