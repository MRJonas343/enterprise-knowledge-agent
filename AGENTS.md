# Enterprise Knowledge Agent: Agent Contract

This repository builds an Enterprise Knowledge Agent: grounded enterprise answers over governed knowledge, using Microsoft Foundry, Foundry IQ and Azure services. **Phases 0-3 are accepted: the infrastructure, the knowledge corpus, the synchronization path, cited retrieval and the Foundry agent all work end to end. The acceptance records are in [`docs/verification/`](docs/verification/). The active boundary is the rest of the MVP: FastAPI and the Next.js frontend.**

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
├── enterprise_knowledge_agent/  Python package (uv, src layout)
└── scripts/                     Operational scripts: knowledge sync, knowledge source
                                 and knowledge base creation

docs/                          Project documentation, ADRs, architecture and diagram rules
```

Structure rules that must not drift:

- `enterprise-knowledge/` mirrors the Blob container `enterprise-knowledge`. Paths referenced inside documents are container-relative, for example `architecture/payment-service.md`.
- The Git corpus is the source of truth. Documents are never edited directly in Azure.
- Terraform owns control-plane resources only. Knowledge sources and knowledge bases are Azure AI Search data-plane objects and are created by the scripts in `src/scripts/`, never by Terraform or azapi.

## Current Boundary: Phase 4-5, the MVP Path

Phases 0 to 3 are accepted. The Phase 2 retrieval gate and the Phase 3 agent gate were both cleared on 2026-09-19; the evidence is in [`docs/verification/`](docs/verification/).

The active boundary is the rest of the MVP path:

- Phase 3: Foundry Agent Service integrated with the knowledge base. Accepted 2026-09-19.
- Phase 4: FastAPI application gateway. Not started.
- Phase 5: Next.js frontend. Not started.

The MVP completes when the end-to-end agent, API and UI path works, so Phases 4 and 5 remain.

Two findings from the Phase 3 record are direct inputs to Phase 4. Citation annotations carry the correct source URL and text span, but `title` duplicates the URL and `file_id`, `tool_name` and `snippet` are unpopulated, so the API contract must not assume a human-readable title exists. And `run_agent.py` prints only `result.text`, leaving `【N:M†source】` markers that a reader cannot resolve, so surfacing citations is a contract requirement rather than a client detail.

**Hard gate:** evaluations, observability implementation, security hardening, prompt-injection defenses, SharePoint and other post-MVP work stay behind the MVP gate. Do not start them while Phases 4 and 5 are open. Read the acceptance records before changing anything that affects grounding, citations or the knowledge source.

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
| MVP gate | End-to-end agent/API/UI path, MCP/tool policy, observability, evaluation evidence, and security acceptance are complete per the roadmap | Post-MVP expansion |

Each gate needs a dated verification note or linked change record. A plan, mock, or unverified preview response is not acceptance evidence.

## Architecture Boundaries

- Foundry IQ is the primary retrieval intelligence layer for the MVP. Do not build custom retrieval orchestration, ranking, chunking, or citation plumbing around it unless an accepted ADR documents a verified gap.
- Blob Storage is the primary Phase 2 knowledge source. Markdown is version-controlled locally and synchronized reproducibly; it is not edited ad hoc in Azure.
- Terraform is the infrastructure source of truth from day one. Do not create unmanaged Azure resources to make a test pass.
- Foundry IQ retrieval, Blob Storage and Foundry Agent Service are implemented. FastAPI and the Next.js frontend are the remaining MVP targets. Operational MCP tools, OpenTelemetry, evaluations, security hardening and SharePoint are later boundaries described in the roadmap.
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
- Use least privilege and secure defaults when a phase permits security implementation; before Phase 2, limit work to safe bootstrap hygiene and retrieval prerequisites.
- Storage is keyless. `shared_access_key_enabled = false` only works together with `storage_use_azuread = true` in the provider block, because the provider makes its own data-plane calls while managing the account. Never re-enable shared keys to get past a failure; fix the identity path instead.
- Azure AI Search also runs keyless (`local_authentication_enabled = false`), so the operator needs Search Service Contributor and Search Index Data Contributor rather than admin API keys.

### Security and data

- Treat enterprise documents, prompts, citations, logs, and evaluation fixtures as potentially sensitive.
- Redact secrets and personal data from examples, logs, screenshots, and test fixtures.
- Do not upload real confidential documents for local validation without explicit authorization.
- Do not begin the security-hardening phase before Phase 2 acceptance, but never weaken credential hygiene to unblock Phase 2.

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

Current status: Phases 0-3 accepted on 2026-09-19. The next owner should build the FastAPI gateway (Phase 4) and the Next.js frontend (Phase 5) to reach the MVP gate. Everything the knowledge base and the agent need already exists: `enterprise-knowledge/` is the source corpus, `infra/terraform/` owns the Azure control plane, and `src/scripts/` owns the data-plane objects. The Phase 3 acceptance record carries two contract inputs for Phase 4: citation annotations resolve to a source URL and text span but have no human-readable title, and the terminal client does not resolve citation markers, so surfacing citations is an API requirement. Evaluations, observability, security hardening and SharePoint remain behind the MVP gate.
