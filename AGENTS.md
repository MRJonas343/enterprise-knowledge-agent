# Enterprise Knowledge Agent: Agent Contract

This repository builds an Enterprise Knowledge Agent: grounded enterprise answers over governed knowledge, using Microsoft Foundry, Foundry IQ and Azure services. **Phases 0-5 are accepted and the MVP is complete: the infrastructure, the knowledge corpus, the synchronization path, cited retrieval, the Foundry agent, the FastAPI gateway and the Next.js frontend work end to end. The roadmap defines the MVP as phases 3-5, and all three gates are cleared.** The acceptance records are in [`docs/verification/`](docs/verification/).

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

## Current Boundary: MVP Complete, Post-MVP Not Started

Phases 0 to 5 are accepted and the MVP is complete. All five gates were cleared on 2026-09-19; the evidence is in [`docs/verification/`](docs/verification/).

The MVP is defined by the roadmap as phases 3 to 5, and that is what is complete:

- Phase 3: Foundry Agent Service integrated with the knowledge base. Accepted 2026-09-19.
- Phase 4: FastAPI application gateway. Accepted 2026-09-19.
- Phase 5: Next.js frontend in `frontend/`. Accepted 2026-09-19.

The end-to-end path was verified with a live request carrying a browser origin: a question submitted through the frontend's own request path reached the gateway, the agent, and the knowledge base, and the returned citations rendered as source links.

**Completing the MVP is not the same as being production-ready.** Operational MCP tools, prompt-injection defenses, security hardening, evaluations, CI/CD and SharePoint are phases 6 to 15 and remain unstarted, and observability reaches only as far as the two narrow exceptions recorded below. The MVP proves the path works; those phases would prove it can be operated.

Two limitations carried forward from Phase 5. The interactive browser flow was never driven in a real browser — requests were made from the frontend's own modules against a live gateway, which is close but not the same. And citation offsets are produced by a Python process and applied by JavaScript, so they would misalign if a non-BMP character ever entered an answer.

**Hard gate:** do not start post-MVP work (phases 6-15) before this boundary is explicitly superseded. Read the acceptance records before changing anything that affects grounding, citations or the knowledge source.

### Narrow exception: the grounding probe fixture

One piece of evaluation-adjacent work was explicitly authorized by the project owner before the boundary was superseded, and it is recorded here so it is not mistaken for a general opening of Phase 11.

`tests/fixtures/grounding-probes.yaml` and `tests/run_probes.py` turn the four adversarial probes that Phase 2 and Phase 3 ran by hand into a repeatable regression check. They protect grounding against a prompt or retrieval-configuration change; they are not an evaluation suite. There is no groundedness scoring, no relevance metric, no regression fixture store and no latency or cost measurement, so Phase 11 remains unstarted.

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
| MVP gate | Foundry Agent Service, FastAPI and Next.js provide a working end-to-end grounded user path. The MVP is complete only once that path works. **Met 2026-09-19**: phases 3-5 accepted, evidence in [`docs/verification/`](docs/verification/) | Post-MVP expansion (phases 6-15) |

Each gate needs a dated verification note or linked change record. A plan, mock, or unverified preview response is not acceptance evidence.

## Architecture Boundaries

- Foundry IQ is the primary retrieval intelligence layer for the MVP. Do not build custom retrieval orchestration, ranking, chunking, or citation plumbing around it unless an accepted ADR documents a verified gap.
- Blob Storage is the primary Phase 2 knowledge source. Markdown is version-controlled locally and synchronized reproducibly; it is not edited ad hoc in Azure.
- Terraform is the infrastructure source of truth from day one. Do not create unmanaged Azure resources to make a test pass.
- Foundry IQ retrieval, Blob Storage, Foundry Agent Service, the FastAPI gateway and the Next.js frontend are all implemented. Operational MCP tools, OpenTelemetry, evaluations, security hardening and SharePoint are later boundaries described in the roadmap.
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
- Do not begin the security-hardening phase before the current post-MVP boundary is explicitly superseded, and never weaken credential hygiene to unblock a phase.

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

Current status: Phases 0-5 accepted on 2026-09-19 and the MVP is complete. The end-to-end path works and the acceptance records are in [`docs/verification/`](docs/verification/). Everything needed is in place: `enterprise-knowledge/` is the source corpus, `infra/terraform/` owns the Azure control plane, `src/scripts/` owns the data-plane objects, `src/enterprise_knowledge_agent/api.py` serves `POST /api/chat` and `GET /api/health`, and `frontend/` renders answers with citations resolved from span data. Post-MVP work (phases 6-15) should not begin until the current boundary is explicitly superseded; the next owner should decide which post-MVP phase to take first, and no phase has a dependency on another yet at that boundary. Two caveats to carry forward: the interactive browser flow was never driven in a real browser, and citation offsets would misalign if a non-BMP character entered an answer.
