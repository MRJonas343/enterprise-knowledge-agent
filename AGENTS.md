# Enterprise Knowledge Agent: Agent Contract

This repository builds an Enterprise Knowledge Agent: grounded enterprise answers over governed knowledge, using Microsoft Foundry, Foundry IQ and Azure services. **Phases 0-9, 11 and 13 are accepted and the MVP is complete: the infrastructure, the knowledge corpus, the synchronization path, cited retrieval, the Foundry agent, the FastAPI gateway and the Next.js frontend work end to end. The roadmap defines the MVP as phases 3-5, and all three gates are cleared; Phase 9, Security, Phase 11, Evaluations, and Phase 13, CI/CD, are accepted on top of them.** The acceptance records are in [`docs/verification/`](docs/verification/).

## Quick Path

1. Read [`docs/README.md`](docs/README.md) for the documentation map.
2. Read [`docs/development-roadmap.md`](docs/development-roadmap.md) and confirm the active phase before changing anything.
3. Read [`docs/agent-guidelines.md`](docs/agent-guidelines.md) before planning or implementing work.
4. For architecture decisions, read [`docs/project-context.md`](docs/project-context.md), [`docs/architecture/README.md`](docs/architecture/README.md), and the relevant ADR.
5. Update documentation and ADRs when an implementation changes an approved boundary.

## Repository Structure

```text
enterprise-knowledge/          Version-controlled enterprise document corpus
├── architecture/              Service and system documentation
├── runbooks/                  Operational response procedures
├── incidents/                 Post-incident reports (INC-YYYY-NNN)
├── engineering/               Deployment and rollback policy
└── security/                  Security policy

infra/terraform/               Azure infrastructure (azurerm, canadacentral)
├── main.tf                    Resource group, Foundry account, project, model deployments
├── storage.tf                 Storage account, knowledge container, storage RBAC
├── search.tf                  Azure AI Search and search RBAC
├── providers.tf               Provider configuration, including storage_use_azuread
├── variables.tf               Every variable input
└── outputs.tf                 Values consumed by the Python scripts

src/
├── enterprise_knowledge_agent/  Python package (uv, src layout): the agent client
│                                and the FastAPI gateway
└── scripts/                     Operational scripts: knowledge sync, knowledge source
                                 and knowledge base creation

frontend/                      Next.js application: question surface and citation
                               inspection

tests/                         Gateway contract tests (no Azure required) and the
                               grounding probes (live Azure)

assets/                        Screenshots referenced by the README

docs/                          Project documentation, ADRs, architecture and diagram rules
```

Structure rules that must not drift:

- `enterprise-knowledge/` mirrors the Blob container `enterprise-knowledge`. Paths referenced inside documents are container-relative, for example `architecture/payment-service.md`.
- The Git corpus is the source of truth. Documents are never edited directly in Azure.
- Terraform owns control-plane resources only. Knowledge sources and knowledge bases are Azure AI Search data-plane objects and are created by the scripts in `src/scripts/`, never by Terraform or azapi.

## Current Boundary: Phases 9, 11 and 13 Accepted

Phases 0 to 9, 11 and 13 are accepted and the MVP is complete. The MVP gates were cleared on 2026-09-19, Phase 9 was accepted on 2026-09-20 and Phase 11, Evaluations, and Phase 13, CI/CD, were accepted the same day; the evidence is in [`docs/verification/`](docs/verification/).

**The post-MVP boundary was explicitly superseded on 2026-09-20 by the project owner, who selected Phase 9, Security, as the next phase. Phase 9 is now accepted.** Phase 13, CI/CD, is also accepted: a validation pipeline runs on every push and pull request. The remaining roadmap is Phase 12: observability. Phases 6, 7, 8, 10, 14 and 15 are retired: the agent's only tool is the knowledge base, executed server side by Foundry Agent Service, so the operational-tool framework (7) and MCP (8) would have no consumer, and the rest were cut as out of scale or already owned by Foundry IQ. No post-MVP boundary is currently active.

Phase 9 depended only on Phase 5 MVP completion, the same single dependency the post-MVP phases carry. Retiring Phase 7 removed the only other prerequisite its row named, so the phase was bounded entirely by what already existed: the gateway, the agent, the knowledge source and the credentials around them.

Phase 9 is deliberately narrower than its original roadmap row. Network and data controls, data retention and audit logging are out of scope, and the reasoning is recorded in the roadmap's Work Record. The short version: they are infrastructure-hardening concerns with no place in a portfolio-scale RAG demonstration, the network work would break the operator's local development path, and agent tracing gives a partial view of what the agent ran — though, being trace spans rather than an access log, no view of who asked.

The end-to-end path was verified with a live request carrying a browser origin: a question submitted through the frontend's own request path reached the gateway, the agent, and the knowledge base, and the returned citations rendered as source links.

**Completing the MVP is not the same as being production-ready, and neither is completing Phase 9 or Phase 11.** Observability (Phase 12) remains unstarted, and observability reaches only as far as the two narrow exceptions recorded below. CI/CD now exists as a validation pipeline, but it builds no artifact and deploys nothing. Phase 11 is accepted at Tier 1 only: deterministic checks with no LLM judge and no relevance metric. Prompt-injection defenses were retired as a phase, but the threat carries into Phase 11 as an evaluation criterion: a poisoned document must not change an answer, and that experiment has not yet been run. Phase 9 was the first move from "the path works" toward "it can be operated", and it is accepted only for the scope recorded in its verification note.

One limitation carried forward from Phase 5, and one that was closed after it. Citation offsets are produced by a Python process and applied by JavaScript, so they would misalign if a non-BMP character ever entered an answer. The interactive browser flow, which the Phase 5 record left unverified, was subsequently driven by the project owner and works. That amendment is recorded in the Phase 5 acceptance record.

**Boundary rule:** read the acceptance records before changing anything that affects grounding, citations or the knowledge source, and keep every phase gate's evidence honest about what it did and did not verify.

### Narrow exception: the grounding probe fixture

One piece of evaluation-adjacent work was explicitly authorized by the project owner before the boundary was superseded, and it is recorded here so it is not mistaken for a general opening of Phase 11.

`tests/fixtures/grounding-probes.yaml` and `tests/run_probes.py` turn the four adversarial probes that Phase 2 and Phase 3 ran by hand into a repeatable regression check. They protect grounding against a prompt or retrieval-configuration change; they are not an evaluation suite. The probes themselves carry no groundedness scoring, no relevance metric, no regression fixture store and no latency or cost measurement, so the exception did not open Phase 11.

The probes are the canonical wording. Other documents should point to the fixture rather than restating the questions, because the same probe had drifted into three different phrasings across the acceptance records and the README.

### Narrow exception: agent tracing

One piece of observability work was explicitly authorized by the project owner before the boundary was superseded, and it is recorded here so it is not mistaken for a general opening of Phase 12.

`infra/terraform/tracing.tf` provisions a Log Analytics workspace and an Application Insights resource, and `src/scripts/link_tracing.py` connects the second to the Foundry project. Agent runs are then traced and readable in the Foundry portal as spans: the tool call, the model call, their durations and their payloads.

That is the agent's own trace and nothing more. There are no metrics, no logs, no correlation identifiers across service boundaries, no alerting and no redaction policy, so Phase 12 remains unstarted.

The tracing path is keyless: local authentication is disabled on both resources, the project identity publishes through `Monitoring Metrics Publisher`, and reading the tool payloads needs `Privileged Monitoring Data Reader`. The project connections API nevertheless requires the Application Insights connection string to identify its target, so the script supplies one. It identifies and does not authenticate.

## Source-of-Truth Precedence

When sources disagree, use this order and record meaningful deviations:

1. Explicit user/product brief: product intent, priority, scope, and non-negotiable decisions.
2. Current official Microsoft documentation and verified, pinned SDK/API versions: actual service behavior and supported configuration.
3. Accepted ADRs in this repository: repository decisions that operationalize the brief.
4. Code, tests, Terraform state/configuration, and observed service behavior: the implemented truth once those exist.
5. Agent assumptions or generated examples: never authoritative without verification.

Preview or evolving Foundry IQ and Foundry APIs require a dated documentation check, version/assumption record, and an ADR update before implementation relies on them.

## Phase Gates

| Gate | Required evidence | Blocks |
| --- | --- | --- |
| Phase 0 | Repository contract, roadmap, context, architecture index, and initial ADRs are coherent | Phase 1 changes without documented intent |
| Phase 1 | Terraform plan/apply is reproducible in the approved environment, with no secrets in code or state workflow | Phase 2 source synchronization |
| Phase 2 retrieval acceptance | Version-controlled Markdown is synchronized to Blob Storage; a Blob-backed Foundry IQ Knowledge Base returns a successful answer with citations; assumptions and versions are recorded. **Met 2026-09-19**: see [`docs/verification/phase-2-retrieval-acceptance.md`](docs/verification/phase-2-retrieval-acceptance.md) | Satisfied |
| Phase 3 agent acceptance | Agent behaviour is verified against the accepted retrieval path, with service/API versions, citation preservation and failure behaviour documented. **Met 2026-09-19**: see [`docs/verification/phase-3-agent-acceptance.md`](docs/verification/phase-3-agent-acceptance.md) | Satisfied |
| Phase 4 API acceptance | The gateway contract and integration checks cover successful grounded answers, missing context, service failure and citation preservation. **Met 2026-09-19**: see [`docs/verification/phase-4-api-acceptance.md`](docs/verification/phase-4-api-acceptance.md) | Satisfied |
| Phase 5 frontend acceptance | A user can submit a question and inspect grounded citations through the API; the complete agent/API/UI path works without exposing secrets. **Met 2026-09-19**: see [`docs/verification/phase-5-frontend-acceptance.md`](docs/verification/phase-5-frontend-acceptance.md) | Satisfied |
| Phase 9 security acceptance | Identity boundaries, least privilege, credential externalization and the guardrail are verified end to end, and every known risk has a control and a disposition. **Met 2026-09-20**: see [`docs/verification/phase-9-security-acceptance.md`](docs/verification/phase-9-security-acceptance.md) | Satisfied |
| Phase 13 CI/CD acceptance | Changes are validated automatically before merge across the three layers of the repository, a failure names the layer that broke, and the pipeline holds no credentials or write access. **Met 2026-09-20**: see [`docs/verification/phase-13-cicd-acceptance.md`](docs/verification/phase-13-cicd-acceptance.md) | Satisfied |
| Phase 11 evaluations acceptance | Evaluation evidence is reproducible, known failures are tracked, and changes are compared with baselines. **Met 2026-09-20**: see [`docs/verification/phase-11-evaluations-acceptance.md`](docs/verification/phase-11-evaluations-acceptance.md) | Satisfied |
| MVP gate | Foundry Agent Service, FastAPI and Next.js provide a working end-to-end grounded user path. The MVP is complete only once that path works. **Met 2026-09-19**: phases 3-5 accepted, evidence in [`docs/verification/`](docs/verification/) | Post-MVP expansion (phase 12) |

Each gate needs a dated verification note or linked change record. A plan, mock, or unverified preview response is not acceptance evidence.

## Architecture Boundaries

- Foundry IQ is the primary retrieval intelligence layer for the MVP. Do not build custom retrieval orchestration, ranking, chunking, or citation plumbing around it unless an accepted ADR documents a verified gap.
- Blob Storage is the primary Phase 2 knowledge source. Markdown is version-controlled locally and synchronized reproducibly; it is not edited ad hoc in Azure.
- Terraform is the infrastructure source of truth from day one. Do not create unmanaged Azure resources to make a test pass.
- Foundry IQ retrieval, Blob Storage, Foundry Agent Service, the FastAPI gateway and the Next.js frontend are all implemented. Observability (Phase 12, OpenTelemetry) is the remaining boundary described in the roadmap. Security hardening was completed as Phase 9, evaluations were delivered as Phase 11, and CI/CD was delivered as Phase 13. Runtime tools, MCP, SharePoint, retrieval optimization and advanced infrastructure hardening are retired rather than later: the agent's only tool is the knowledge base, executed server side.
- Any diagram must distinguish implemented, verified, preview, and planned components.

## Engineering Rules

### Coding and testing

- Prefer small, reviewable changes with explicit acceptance evidence.
- Use current, pinned Python/TypeScript/Azure SDK versions after checking official documentation.
- Do not add compatibility shims or abstractions without a concrete consumer or persisted behavior.
- Tests must verify behavior at the current phase boundary; do not create tests for unimplemented future services merely to make the repository look complete.
- Retrieval validation must prove source identity and citations, not only a non-empty answer.

### IaC and Azure

- Terraform owns resource definitions, naming inputs, configuration, and reproducibility.
- Keep environment-specific values in documented variable inputs or approved secret stores; never commit credentials, tokens, connection strings, or private endpoints.
- Record provider versions, API versions, region assumptions, preview flags, and manual prerequisites.
- Use least privilege and secure defaults when a phase permits security implementation.
- Storage is keyless. `shared_access_key_enabled = false` only works together with `storage_use_azuread = true` in the provider block, because the provider makes its own data-plane calls while managing the account. Never re-enable shared keys to get past a failure; fix the identity path instead.
- Azure AI Search also runs keyless (`local_authentication_enabled = false`), so the operator needs Search Service Contributor and Search Index Data Contributor rather than admin API keys.

### Security and data

- Treat enterprise documents, prompts, citations, logs, and evaluation fixtures as potentially sensitive.
- Redact secrets and personal data from examples, logs, screenshots, and test fixtures.
- Do not upload real confidential documents for local validation without explicit authorization.
- Phase 9 security hardening is authorized: the post-MVP boundary was superseded on 2026-09-20. Stay inside the scope recorded in the roadmap, and never weaken credential hygiene to unblock a phase.

## Documentation Rules

- Write technical artifacts in English, with actionable quick paths, headings, tables, and checklists.
- State whether content is implemented, verified, preview/evolving, or planned.
- Update the roadmap status when a phase starts or reaches its gate.
- Add or update an ADR for a durable architectural decision, a changed Azure boundary, or a deliberate deviation from the brief.
- Keep diagrams evidence-based and update them with implementation changes; see [`docs/diagrams/README.md`](docs/diagrams/README.md).
- Keep the root `README.md` focused on purpose, architecture and run instructions; it is the public entry point.
- Never commit `.env`, Terraform state, or generated tooling directories. See `.gitignore`.

## Working Phase by Phase

1. Read the phase row, dependencies, exit criteria, and linked ADRs.
2. Verify current Microsoft documentation and record exact versions/assumptions for Azure APIs or SDKs.
3. Make only changes within the active phase and its explicit prerequisites.
4. Run the phase-specific verification, including a clean/reproducible path where applicable.
5. Update status, evidence links, ADRs, and diagrams before moving to the next gate.
6. Stop at the gate if evidence is missing; do not infer acceptance from partial success.

## Handoff Checklist

- [ ] Active phase and allowed scope are named.
- [ ] Source-of-truth conflicts and assumptions are recorded.
- [ ] No secrets or local absolute paths are present.
- [ ] Required verification has run and its evidence is linked.
- [ ] Documentation, ADRs, roadmap status, and diagrams match the implementation.
- [ ] Unimplemented components remain clearly labeled as future work.

## Initial Handoff

Current status: Phases 0-9, 11 and 13 are accepted and the MVP is complete. The MVP gates cleared on 2026-09-19, Phase 9, Security, was accepted on 2026-09-20, with evidence in [`docs/verification/phase-9-security-acceptance.md`](docs/verification/phase-9-security-acceptance.md), and Phase 11, Evaluations, and Phase 13, CI/CD, were accepted the same day. The end-to-end path works and the acceptance records are in [`docs/verification/`](docs/verification/). Everything needed is in place: `enterprise-knowledge/` is the source corpus, `infra/terraform/` owns the Azure control plane, `src/scripts/` owns the data-plane objects, `src/enterprise_knowledge_agent/api.py` serves `POST /api/chat` and `GET /api/health`, and `frontend/` renders answers with citations resolved from span data. The interactive browser flow was subsequently driven by the project owner and works; see the amendment in the Phase 5 record. One caveat remains: citation offsets would misalign if a non-BMP character entered an answer.

Phase 9 (security), Phase 11 (evaluations) and Phase 13 (CI/CD) are accepted and their evidence is linked above; no post-MVP boundary is currently active. Phase 12 (observability) remains unstarted, and Phases 6, 7, 8, 10, 14 and 15 are retired. Two narrow exceptions are recorded above: the grounding probes and agent tracing. Phase 11 carries the two items cut with their phases — the retrieval reasoning-effort experiment from Phase 6 and the poisoned-document threat from Phase 10 — and both experiments remain unrun.
