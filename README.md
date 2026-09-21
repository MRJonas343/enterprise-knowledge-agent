# Enterprise Knowledge Agent

[![CI](https://github.com/MRJonas343/enterprise-knowledge-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MRJonas343/enterprise-knowledge-agent/actions/workflows/ci.yml)

Grounded answers over governed enterprise knowledge, built on **Microsoft Foundry**, **Foundry IQ** and **Azure AI Search**.

The agent answers questions that need evidence from several documents at once, cites the source of every claim, and says so plainly when the knowledge base does not contain the answer.

This is not "upload PDFs and chat with them". It is the engineering *around* retrieval: knowledge-source architecture, ingestion, grounding, citations, agent integration, guardrails, evaluation and reproducible infrastructure.

![The frontend answering the flagship question in dark mode, with numbered citation links](assets/Agent_Test_UI_NextJS.png)

---

## What it demonstrates

| Capability | How |
| --- | --- |
| Agentic RAG over enterprise knowledge | A Foundry IQ knowledge base with agentic retrieval, not a hand-rolled pipeline |
| Multi-source reasoning | A question spanning architecture, a runbook and an incident report is answered from all three |
| Citations that resolve | Every claim maps to the originating document through structured spans, with openable source links |
| Grounding under adversarial input | Fabricated incidents, services and domains are refused rather than invented |
| Guardrails | A Responsible AI policy on the model deployment; a blocked turn is a clear `400`, not a `500` |
| Evaluation without a judge | Groundedness checked deterministically against the version-controlled corpus |
| Keyless by design | No account keys, no API keys, no instrumentation keys anywhere |
| Reproducible infrastructure and content | Terraform owns the control plane; Markdown in Git owns the content |
| CI on every push | Python tests, frontend lint, tests and build, and Terraform format and validate |

---

## Architecture

```mermaid
flowchart TD
    MD["enterprise-knowledge/<br/>version-controlled Markdown"]
    SYNC["sync_knowledge.py"]
    BLOB["Azure Blob Storage<br/>container: enterprise-knowledge"]
    KS["Foundry IQ knowledge source<br/>kind azureBlob"]
    IDX["Generated pipeline<br/>datasource · skillset · indexer · index"]
    KB["Foundry IQ knowledge base"]
    AGENT["Foundry agent<br/>aurora-knowledge-agent"]
    API["FastAPI gateway<br/>POST /api/chat"]
    FRONT["Next.js frontend<br/>citation inspection"]

    MD --> SYNC --> BLOB --> KS --> IDX --> KB
    FRONT --> API
    API -->|"conversation_id + message"| AGENT
    AGENT -->|"MCP: knowledge_base_retrieve"| KB
    KB -->|"grounded chunks + citations"| AGENT
    AGENT -->|"answer + citation spans resolved to URLs"| API
```

Azure resources, all in `canadacentral`:

| Resource | Role |
| --- | --- |
| Microsoft Foundry account and project | Hosts the models and the agent |
| `gpt-5.4-mini` deployment | The agent's reasoning model and the knowledge base query planner |
| `text-embedding-3-large` deployment | Chunk vectorization during ingestion |
| Azure AI Search (Basic) | Hosts the knowledge source, the knowledge base and the generated index |
| Azure Blob Storage | The document corpus at runtime |
| Log Analytics + Application Insights | Agent run spans, and the gateway's own request spans |
| Managed identities and RBAC | Every hop authenticates with Microsoft Entra ID |

The gateway and the frontend run locally; the three components before them are deployed Azure resources.

![Runtime architecture](assets/enterprise-knowledge-agent-runtime.webp)

### Why Foundry IQ, and what it owns

Foundry IQ is the retrieval intelligence layer: chunking, embedding generation, query decomposition, parallel subquery execution, semantic reranking, permission enforcement and citation extraction.

The project deliberately builds **no** custom retrieval orchestration, ranking or citation plumbing. When the knowledge source is created, Foundry IQ generates the whole indexer pipeline — datasource, skillset, indexer and index — from one declarative object.

One consequence is structural: **knowledge sources and knowledge bases are Azure AI Search data-plane objects, not ARM resources.** Terraform cannot manage them, which is why the scripts in `src/scripts/` do. Terraform owns the control plane; the scripts own the data plane.

---

## The flagship question

> Checkout latency increased after a deployment. Based on our architecture documentation, previous incidents and operational runbooks, what are the most likely causes and what should the engineering team investigate first?

No single document answers it. The response drew on four:

| Fact in the answer | Source document |
| --- | --- |
| Synchronous call from checkout-api to payment-service, 2 second timeout, no circuit breaker | `architecture/checkout-service.md` |
| The `settlements` query with no supporting index, pool exhaustion, and the v2.31.0 rollback | `incidents/INC-2026-002.md` |
| The diagnostic path, and the 80% pool utilisation alert threshold | `runbooks/database-latency.md` |

The agent produced a prioritised investigation plan whose citations resolved to real Blob URLs. Across four recorded runs it cited between three and five distinct documents; retrieval returned five or six.

![The agent answering the flagship question, with mcp_list_tools against the knowledge-base server](assets/Portal-Agent-Test_Retrieval.png)

---

**Security.** Callers authenticate at the gateway with bearer tokens; it fails closed, a conversation can only be continued by the caller who opened it, and each caller has a quota. A Responsible AI guardrail sits on the model deployment, with harm categories at a medium threshold plus the binary jailbreak, profanity and protected-material filters. A blocked turn returns `400` with a plain explanation.

![The frontend answering a jailbreak attempt with the gateway's content-safety block](assets/Guardrails_in_action.png)

The guardrail filters the caller's message and the model's completion. It does **not** see the documents the agent retrieves, so it is not an indirect-injection control. The system prompt instead instructs the agent to treat retrieved documents as reference data rather than instructions.

**Evaluation.** `tests/run_evaluations.py` checks groundedness without an LLM judge: because the corpus is version-controlled, it can read the cited documents and verify that the values an answer asserts actually appear in them. Ten factual cases plus four adversarial probes, with a recorded baseline and `--compare-baseline` for regressions.

**Observability.** Foundry writes each agent run as spans, and the gateway exports its own request spans and metrics to the same Application Insights. Sensitive data stays off, so prompts, answers and retrieved documents are never exported.

![The Foundry trace of one agent run, showing the knowledge base tool call and the model call as spans](assets/Tracing-aurora-agent.png)

That run is three spans over 7.7 seconds: the agent invocation, a 4.89 second retrieval call and a 2.31 second model call. Expanding the tool span shows what crossed: the question passed verbatim as a single `query_variants` entry, and `Retrieved 8 documents` in return.

The path stays keyless. Both tracing resources disable local authentication; the project identity publishes through `Monitoring Metrics Publisher`, and reading the GenAI payloads needs `Privileged Monitoring Data Reader`. One string is unavoidable — the project connections API requires the Application Insights connection string to identify its target when the connection is created — and it identifies without authenticating.

---

## Grounding, tested adversarially

Retrieval working does not prove the agent refuses to invent. Four probes, each in a fresh conversation:

| Probe | Result |
| --- | --- |
| A fabricated incident ID (`INC-2026-009`) | Refused, and listed the three incident IDs that do exist |
| An undocumented attribute of a real service (order-service connection pool) | Refused, and avoided transferring the value documented for a different service |
| A fabricated service (`fraud-detection-service`) | Refused, and reported what retrieval had actually returned |
| A domain absent from the corpus (parental leave policy) | Refused with no invention |

Four passing probes are strong evidence of grounding, not proof. They do not cover every hallucination shape, and the poisoned-document case has not been run.

---

## Getting started

**Prerequisites:** an Azure subscription with permission to create resources and role assignments; Terraform 1.x, the Azure CLI, and Python 3.12 with [uv](https://docs.astral.sh/uv/); and the `Foundry User` and `Foundry Project Manager` roles on the Foundry resource.

```bash
# 1. Infrastructure: resource group, Foundry, models, storage, Azure AI Search
cd infra/terraform && terraform init && terraform apply && cd ../..

# 2. Configuration. Fill in what `terraform output` prints.
cp .env.example .env

# 3. Python dependencies
uv sync

# 4. Corpus into Blob Storage
uv run python src/scripts/sync_knowledge.py

# 5. Knowledge source and knowledge base. Waits for ingestion.
uv run python src/scripts/deploy_knowledge_base.py

# 6. The agent, whose only tool is the knowledge base
uv run python src/scripts/deploy_agent.py
```

Then, in two terminals:

```bash
# Terminal A — the gateway
uv run uvicorn enterprise_knowledge_agent.api:app --reload

# Terminal B — the frontend
cd frontend && npm install && npm run dev
```

Open `http://localhost:3000` and ask a question. Steps 1-6 are first-time setup; day to day you only need the two terminals.

### Configuration that is easy to get wrong

- **The frontend needs its own token.** `NEXT_PUBLIC_API_TOKEN` goes in `frontend/.env.local`, not the repository-root `.env` — Next.js only reads `.env*` from its own directory. It must match the token half of an entry in `API_TOKENS`. Because the value is inlined into the browser bundle at build time, restart `next dev` after changing it.
- **The gateway fails closed.** With `API_TOKENS` unset, `POST /api/chat` returns `503` rather than serving unauthenticated callers. Ask with the header:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/chat \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer tok_your_token" \
    -d '{"message":"What are the alert thresholds for PgBouncer pool utilisation?"}'
  ```
- **Watch the endpoints.** The knowledge base needs the bare Foundry resource endpoint (`https://<name>.services.ai.azure.com`). The OpenAI-compatible output ending in `/openai/v1` is for chat clients only; using it for ingestion fails every document with 404s.

`GET /api/health` is unauthenticated. Interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

### The API contract

`POST /api/chat` takes `{message, conversation_id?}` and returns the answer, a `conversation_id`, and a `citations` array. Each citation carries the source URL plus `start_index` and `end_index`, so a client slices the answer text at those offsets and replaces the `【N:M†source】` marker with a link.

Each citation also carries `source_url`: the same document with a short-lived, read-only SAS appended, so the link actually opens. `url` keeps the canonical Blob URL and is never replaced by the SAS, so the identity of a source does not expire with the credential that reaches it.

### Tests

```bash
uv run pytest                     # 90 tests, no Azure required
cd frontend && npm run test && npm run lint && npm run build

uv run python tests/run_evaluations.py --compare-baseline tests/baseline.json
uv run python tests/run_probes.py       # live; needs Azure
```

The first two run in CI. The live suites do not, because CI has no credentials.

---

## Design decisions

Durable choices are recorded as ADRs in [`docs/adr/`](docs/adr/):

- [001](docs/adr/001-use-foundry-iq.md) — Use Foundry IQ as the primary retrieval layer
- [002](docs/adr/002-use-blob-storage-as-primary-knowledge-source.md) — Use Blob Storage as the primary knowledge source
- [003](docs/adr/003-use-terraform-from-day-one.md) — Use Terraform from day one
- [004](docs/adr/004-use-fastapi-as-application-gateway.md) — Use FastAPI as the application gateway
- [005](docs/adr/005-use-mcp-for-runtime-tools.md) — Use MCP for governed runtime tools *(rejected; retired)*
- [006](docs/adr/006-add-sharepoint-only-after-mvp.md) — Add SharePoint only after MVP *(rejected; retired)*

Constraints learned the hard way:

- **Agentic retrieval is regional.** It is not available everywhere, and several regions cannot create new Azure AI Search services at all due to capacity. `canadacentral` was chosen after verifying both.
- **Model availability is per region.** `gpt-5-mini` is not offered in `canadacentral` under any deployment type.
- **Foundry IQ preview objects need the preview SDK.** The stable `azure-search-documents` release does not expose the knowledge base surface at all.
- **The MCP tool must reference the connection's ARM ID**, not its bare name, or the agent fails with `Connection resolution failed`.
- **A severity threshold on a binary content filter disables it.** A jailbreak comes back as `{"detected": true, "filtered": false}` — annotated, never blocked. Azure's own policies declare binary filters without a threshold.
- **The embedding model, container and network mode are immutable** once the knowledge source exists; changing them means recreating it and re-ingesting everything.

---

## Known limitations

Stated plainly, because a portfolio that hides its edges is not worth reading.

- **Citations can be attributed to the wrong document.** The evaluation suite found a real case: the answer was correct, but cited two documents that discuss the subject without naming the specific index. Right answer, unsupported provenance. Recorded in the [Phase 11 acceptance](docs/verification/phase-11-evaluations-acceptance.md), not fixed.
- **A caller cannot be identified from a trace.** The gateway's spans carry the route, status and duration, not who asked. There is no access audit trail.
- **The gateway keeps conversations in memory.** They do not survive a restart, and the session store has no eviction. The rate limiter is per-process.
- **The frontend token is readable by anyone who loads the page.** It authenticates against anonymous callers; it is not a secret from a browser user. A server-side proxy route is the correct fix.
- **Two experiments have not been run**: comparing retrieval reasoning effort against the grounding probes, and the poisoned-document case. Both need the knowledge base rebuilt, so they are operational work rather than code.
- **Citation offsets would misalign if a non-BMP character entered an answer.** The offsets are produced by Python and applied by JavaScript.
- **Not production-ready.** No alerting, no dashboards, no capacity metrics, no deployment: CI validates but builds no artifact and deploys nothing.

---

## Repository layout

```text
enterprise-knowledge/          Document corpus, the source of truth
infra/terraform/               Azure control plane
src/
├── enterprise_knowledge_agent/  The package: agent client and FastAPI gateway
└── scripts/                     Data-plane and operational scripts
frontend/                      Next.js question surface and citation inspection
tests/                         Contract tests, deterministic evaluations, grounding probes
assets/                        Screenshots used by this README
docs/                          Architecture, ADRs, roadmap, verification records
```

The corpus is 13 Markdown documents (about 1 400 lines) written for a fictional SaaS company, deliberately cross-referenced so that facts only cohere when several are read together. Each carries a metadata table the sync script copies into Blob metadata, plus a content hash for change detection. `sync_knowledge.py` is incremental: an unchanged document is skipped, and a removed file leaves a blob that is reported but never deleted silently.

---

## License

[MIT](LICENSE).
