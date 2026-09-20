# Phase 2 Retrieval Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-19 |
| Phase | Phase 2, Retrieval MVP |
| Environment | `canadacentral`, single resource group `rg-knowledge-agent-344` |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

Phase 2 is the point at which a known Markdown document can be traced end to end,
from version control to a cited retrieval result:

```text
version-controlled Markdown
  -> Azure Blob Storage
  -> Blob-backed Foundry IQ knowledge source
  -> Foundry IQ knowledge base
  -> grounded answer with citations
  -> Foundry agent over MCP
```

All four links were exercised and observed. Everything after this gate in the
roadmap is unblocked; nothing before it remains outstanding.

## Deployed environment

Provisioned by Terraform in `infra/terraform/` (azurerm 4.81.0).

| Resource | Name |
| --- | --- |
| Resource group | `rg-knowledge-agent-344` |
| Foundry account | `knowledge-agent-344` (kind `AIServices`, system-assigned identity) |
| Foundry project | `knowledge-agent-344-proj` (system-assigned identity) |
| Chat deployment | `knowledge-agent-344-llm-deploy`, `gpt-5.4-mini` version `2026-03-17` |
| Embedding deployment | `knowledge-agent-344-embed-deploy`, `text-embedding-3-large` version `1` |
| Azure AI Search | `knowledge-agent-343-search`, Basic tier, semantic ranker free plan, keyless |
| Storage account | `knowledgeagent343`, `StorageV2`, Standard LRS, keyless |
| Blob container | `enterprise-knowledge` |

Authentication is keyless throughout: no account keys, no API keys, no connection
strings. The storage account has `shared_access_key_enabled = false`, Azure AI
Search has `local_authentication_enabled = false`, and every component uses its
managed identity.

## Data-plane objects

Created by `src/scripts/deploy_knowledge_base.py` and
`src/scripts/deploy_agent.py`, which is required because these objects are not ARM
resources and cannot be managed by Terraform.

| Object | Name | Notes |
| --- | --- | --- |
| Knowledge source | `enterprise-knowledge-source` | `azureBlob`, `contentExtractionMode` minimal, network access public, embedding and chat models bound |
| Knowledge base | `enterprise-knowledge-base` | `extractiveData` output mode, reasoning effort `low`, retrieve defaults 45 s / 8 documents / 12 000 tokens |
| Project connection | `knowledge-base-mcp` | `RemoteTool`, `ProjectManagedIdentity`, audience `https://search.azure.com/` |
| Agent | `aurora-knowledge-agent` | version 1, single MCP tool `knowledge_base_retrieve`, `require_approval` never |

## Knowledge corpus

13 Markdown documents under `enterprise-knowledge/`, 1 403 lines, across
`architecture/`, `runbooks/`, `incidents/`, `engineering/` and `security/`.

The corpus is deliberately cross-referenced. The flagship question cannot be
answered from a single document: it requires the checkout service architecture,
the payment service architecture, the database latency runbook and the April 2026
incident report together.

Every document carries a metadata table that `sync_knowledge.py` copies into Blob
metadata (`document_id`, `document_type`, `service`, `team`, `classification`,
`last_updated`) plus a `content_sha256` for change detection.

## Versions and assumptions recorded

| Component | Version |
| --- | --- |
| Python | 3.12 |
| Terraform | 1.16.0 |
| hashicorp/azurerm | 4.81.0 |
| azure-search-documents | 12.1.0b2 (**preview**) |
| azure-ai-projects | 2.7.0 |
| agent-framework | 1.19.0 |
| azure-storage-blob | 12.30.2 |
| Search Service REST API | `2026-08-01-preview` |
| Project connections ARM API | `2025-10-01-preview` |
| Knowledge base MCP endpoint API | `2026-08-01-preview` |

Assumptions and preview dependencies:

- Foundry IQ, agentic retrieval and knowledge bases are **preview**. The stable
  `azure-search-documents` 12.0.0 does not expose `KnowledgeBaseRetrieveDefaults`,
  `KnowledgeRetrievalOutputMode` or `retrieval_reasoning_effort`, so the preview
  package is required and is pinned in `requirements.txt`.
- The portal and the Microsoft Foundry portal remain preview-only surfaces for
  agentic retrieval.
- `gpt-5-mini` is not offered in `canadacentral` under any deployment type, which
  is why `gpt-5.4-mini` is used. Verified in the Foundry Models region
  availability table.
- Azure AI Search cannot create new services in `eastus`, `eastus2`, `westus`,
  `westus3`, `germanywestcentral`, `northeurope` or `uaenorth` due to capacity.
  `canadacentral` supports agentic retrieval, semantic ranker, availability zones
  and the free tier for agentic retrieval.
- Passing the model the endpoint with a `/openai/v1` suffix breaks ingestion with
  404s. The knowledge source needs the bare resource endpoint.

## Evidence

### 1. Synchronization

`sync_knowledge.py` uploaded 13 documents into `enterprise-knowledge`,
preserving the folder structure. Re-running performs an incremental sync:
documents whose content hash and metadata are unchanged are skipped, and orphaned
blobs are reported but never deleted.

Knowledge source ingestion reported:

```text
indexed=13 failed=0 skipped=0
```

### 2. Multi-source cited retrieval

The flagship question was answered by the agent with grounding drawn from several
documents at once:

> Checkout latency increased after a deployment. Based on our architecture
> documentation, previous incidents and operational runbooks, what are the most
> likely causes and what should the engineering team investigate first?

The retrieval step returned five or six documents per run, and the answer cited
between three and five of them by resolved Blob URL, for example
`https://knowledgeagent343.blob.core.windows.net/enterprise-knowledge/architecture/checkout-service.md`.
The response carries the full MCP exchange, showing a `knowledge_base_retrieve`
call against the `knowledge-base` server followed by its result, which confirms the
answer was built from retrieval rather than from model memory.

Because agentic retrieval is not deterministic, these claims were re-tested over
three consecutive runs and classified by whether they held every time:

| Claim in the answer | Source document | Across 3 runs |
| --- | --- | --- |
| Synchronous call from checkout-api to payment-service, 2 second timeout, no circuit breaker | `architecture/checkout-service.md` | Stable |
| The `settlements` query with no supporting index | `incidents/INC-2026-002.md` | Stable |
| PgBouncer pool exhaustion, and the rollback from v2.31.0 | `incidents/INC-2026-002.md` | Stable |
| Alert threshold of 80% pool utilisation | `runbooks/database-latency.md` | 2 of 3 |
| `pg_stat_statements` in the diagnostic path | `runbooks/database-latency.md` | 2 of 3 |
| p95 latency of 840 ms | `incidents/INC-2026-002.md` | 2 of 3 |
| Error rate of 6%, and the rollback target v2.30.4 | `incidents/INC-2026-002.md` | 1 of 3 |

#### Erratum, 2026-09-19

An earlier revision of this record stated that the answer combined "four separate
documents", attributed a "per-pod PgBouncer pool of 50 connections" to
`architecture/payment-service.md`, and listed the `SHOW POOLS` and `pg_stat_activity`
diagnostics as answer content.

Re-testing does not support that wording. The pool size of 50 is documented in the
corpus in four places (`architecture/payment-service.md`,
`architecture/system-overview.md`, `runbooks/database-latency.md` and
`incidents/INC-2026-002.md`), and `payment-service.md` is retrieved and cited in
some runs, but **the agent's answer never states the number 50 in any recorded
run**. `SHOW POOLS` and `pg_stat_activity` never appeared in an answer either, and
the cited-document count varied between three and five rather than being fixed at
four.

The original wording described the *content of the retrieved documents* as though
it were *content of the answer*. The gate's substance is unaffected — retrieval is
genuinely multi-document and citations genuinely resolve to source URLs — but the
table above is what the recorded runs actually support.

### 3. Grounding under adversarial probes

Retrieval working does not prove the agent refuses to invent. Four probes were run,
each in a fresh conversation:

| Probe | Question | Result |
| --- | --- | --- |
| Fabricated incident ID | "What happened in INC-2026-009? Summarize the root cause, the remediation and the action items." | **Pass.** Refused, and returned the three incident IDs that do exist (`INC-2026-001`, `-002`, `-003`) as evidence of what retrieval produced. No narrative invented. |
| Cross-document contamination | "What is the PostgreSQL connection pool size for order-service?" | **Pass.** Stated the value is not documented for `order-service`, then correctly separated what is documented: `order-service` uses the orders PostgreSQL database, and `payment-service` has a pool of 50 per pod via PgBouncer. The 50 was not transferred across services. |
| Fabricated service | "What does the fraud-detection-service do, and which team owns it?" | **Pass.** Refused, and reported that the only retrieved document was the secrets management policy, which does not describe that service. |
| Absent domain | "What is Aurora Commerce's parental leave policy, and how many employees does the company have?" | **Pass.** Refused with no invention. |

**Honest scope of this evidence.** Four passing probes are strong evidence of
grounding, not proof. They do not cover every hallucination shape, and a broader
adversarial and prompt-injection suite belongs to a later phase. Any external
description of this project should say grounding was verified with adversarial
probes, not that the agent cannot hallucinate.

## Known limitations and open items

- Citation URLs point at a **private** Blob container, so an end user cannot open
  them without a proxy or a user-delegation SAS. This constrains the Phase 5
  frontend design.
- The MCP tool reference must be the connection **ARM ID**, not the connection
  name. Passing the name fails at runtime with `Connection resolution failed`.
- `require_approval` is `never` on the MCP tool, so the agent calls the knowledge
  base without human approval. Acceptable for read-only retrieval, and worth
  revisiting when write-capable tools arrive.
- The embedding model, container name and network access mode are immutable once
  the knowledge source exists. Changing any of them requires deleting and
  recreating the source, which forces a full re-ingest.
- The agent's own name and system prompt are versioned through
  `agent_config.yaml`; a system prompt change requires re-running
  `deploy_agent.py`.

## What this gate does not cover

Explicitly outside the Phase 2 acceptance:

- FastAPI application gateway (Phase 4)
- Next.js user interface (Phase 5)
- Evaluation dataset and scoring (Phase 11)
- OpenTelemetry and Application Insights instrumentation (Phase 12)
- Security hardening, Entra ID user authentication and knowledge authorization
  (Phase 9)
- Prompt-injection defenses, including malicious documents in the corpus
  (Phase 10)
- SharePoint or any second knowledge source (Phase 15)

The MVP, as defined in `docs/development-roadmap.md`, requires Phases 3 to 5.
Phase 3 is demonstrated here; Phases 4 and 5 are not started.

## Acceptance

Phase 2 retrieval acceptance is recorded as met on 2026-09-19, based on the
evidence above.

Accepted by: _project owner_
