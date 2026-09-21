# Development Roadmap

This roadmap is the staged implementation contract for the Enterprise Knowledge Agent. It preserves the requested order from foundation through the retrieval gate, then the end-to-end MVP, then post-MVP expansion. **Phases 0-9, 11 and 13 are accepted and the MVP is complete. The MVP gates cleared on 2026-09-19, and Phase 9, Security, was selected on 2026-09-20 and accepted the same day; Phase 11, Evaluations, and Phase 13, CI/CD, were accepted on 2026-09-20. Phase 12 remains unstarted; Phases 6, 7, 8, 10, 14 and 15 are retired.**

## Status Legend

- **In progress:** work is authorized for this phase, either because the boundary was superseded for it or because it was explicitly selected.
- **Accepted:** the phase gate is cleared and dated evidence is recorded in `docs/verification/`.
- **Next:** authorized only after the preceding phase gate is accepted.
- **Planned:** documented for sequencing, not authorized now.
- **Post-MVP:** starts only after the Phase 5 end-to-end MVP is complete.

## Milestone Gates

| Milestone | Phases | Gate |
| --- | --- | --- |
| Foundation | 0 | Repository and environment conventions are coherent, reviewable, and ready for reproducible implementation. |
| Infrastructure and knowledge source | 1 | Terraform-managed Azure resources, the Blob source, synchronization, and the Blob-backed Foundry IQ Knowledge Base are configured reproducibly. |
| Retrieval acceptance | 2 | Retrieval quality, citations, exact source IDs, semantic queries, and multi-document retrieval pass the hard acceptance criteria. |
| MVP | 3-5 | Foundry Agent Service, FastAPI, and Next.js provide a working end-to-end grounded user path. MVP is complete only after this path works. |
| Post-MVP | 12 | Observability is production-shaped. |

**Phase 12 is post-MVP; Phases 6, 7, 8, 10, 14 and 15 are retired. The post-MVP boundary was superseded on 2026-09-20, Phases 9, 11 and 13 are now accepted, no post-MVP boundary is currently active, and every remaining post-MVP phase stays unstarted until it is explicitly selected.**

## Phase Sequence

| Phase | Scope and deliverables | Dependencies | Exit criteria | Status |
| --- | --- | --- | --- | --- |
| 0 Foundation | Repository structure, Terraform structure, naming conventions, environment configuration, Azure authentication approach, and linting/testing baseline. | None | The repository contract, phase gates, naming and environment conventions, authentication approach, and baseline checks are documented and internally consistent; no implementation is claimed. | **Accepted** |
| 1 Infrastructure + Knowledge Source | Terraform Azure foundation; Blob Storage and container; AI Search; Foundry resources; initial enterprise documents; a deterministic synchronization script; and the Blob-backed Foundry IQ knowledge source and Knowledge Base. | Phase 0; current Microsoft documentation and verified provider/API versions | A clean operator can reproduce the approved foundation, synchronize the approved initial documents, and configure the Blob-backed Foundry IQ Knowledge Base from documented inputs without secrets in the repository. | **Accepted** |
| 2 Retrieval MVP | Retrieval quality, grounded citations, exact source/document IDs, semantic queries, and multi-document retrieval over the Phase 1 knowledge source. | Phase 1; current Foundry IQ/API verification and a known source corpus | The same known documents can be traced through version control, Blob, the Foundry IQ Knowledge Base, and retrieval results; quality and citation checks pass; Phase 2 acceptance is recorded as a hard gate. | **Accepted 2026-09-19**: hard gate cleared; evidence in `docs/verification/phase-2-retrieval-acceptance.md` |
| 3 Foundry Agent MVP | Foundry Agent Service integration for grounded interaction and conversation state, using Foundry IQ as the retrieval intelligence layer. | Phase 2 retrieval acceptance | Agent behavior is verified against the accepted retrieval path, with service/API versions, citation preservation, and failure behavior documented. | **Accepted 2026-09-19**: evidence in `docs/verification/phase-3-agent-acceptance.md` |
| 4 FastAPI Backend | Stable API boundary, request/response contracts, error mapping, and integration with the approved Foundry Agent path. | Phase 3 | Contract and integration checks cover successful grounded answers, missing context, service failure, and citation preservation. | **Accepted 2026-09-19**: evidence in `docs/verification/phase-4-api-acceptance.md` |
| 5 Next.js Frontend | Next.js/TypeScript question-and-answer surface, citation inspection, loading and error states, and responsive behavior. | Phase 4 | A user can submit a question and inspect grounded citations through the API; the complete agent/API/UI path works without exposing secrets. This is the MVP completion gate. | **Accepted 2026-09-19**: evidence in `docs/verification/phase-5-frontend-acceptance.md` |
| 6 Retrieval optimization | Measured improvements to retrieval quality, relevance, latency, and cost without replacing Foundry IQ or weakening citation and grounding guarantees. | Phase 5 MVP completion; Phase 2 regression baseline | Optimizations are measured against the accepted retrieval baseline and documented without regressing source identity, citations, or groundedness. | **Retired 2026-09-20.** Foundry IQ owns retrieval and the only real knob is a knowledge-base setting rather than code, and without the Phase 11 measurement harness an optimization cannot be shown to be an improvement; its single experiment carries forward into Phase 11. See the Work Record. |
| 7 Dynamic operational tools | Explicitly approved operational tools, schemas, authorization boundaries, timeouts, auditability, and failure semantics. Tools are separate from the retrieval layer. | Phase 5 MVP completion; approved tool contracts and security inputs | Tool calls are schema-validated, denied by default, auditable, bounded, and covered by positive and negative tests. | **Retired 2026-09-20.** The agent's only tool is the knowledge base, executed server side by Foundry Agent Service, so a local operational-tool framework has no consumer. See the Work Record. |
| 8 MCP | Governed MCP exposure for approved operational tools, including server boundaries, schemas, authorization, timeouts, and failure handling. MCP is not a substitute for Foundry IQ retrieval. | Phase 7; Phase 9 security direction may constrain rollout | MCP tool behavior is interoperable, policy-controlled, observable, and tested without broadening the approved tool set implicitly. | **Retired 2026-09-20.** MCP would only expose the retired operational tools, adding an indirection layer over retrieval that Foundry IQ already performs. See the Work Record. |
| 9 Security | Identity boundaries, least privilege, secrets handling, and threat-model follow-through. | Phase 5 MVP completion | Security controls are evidenced, credentials remain externalized, protected content is denied safely, and governance risks have owners and mitigations. | **Accepted 2026-09-20**: evidence in [`docs/verification/phase-9-security-acceptance.md`](verification/phase-9-security-acceptance.md) |
| 10 Prompt-injection defenses | Threat-informed prompt-injection defenses for retrieved content, user input, tools, citations, and agent instructions. | Phase 9 security controls; accepted agent and tool surfaces | Injection cases are represented in authorized test fixtures, defenses fail safely, and mitigations do not silently bypass citations or authorization. | **Retired 2026-09-20.** The guardrail covers direct injection and the indirect path is bounded by the agent having one read-only tool, while the platform control for retrieved content is not verifiable through this retrieval path; the threat stays in scope as a Phase 11 evaluation criterion. See the Work Record. |
| 11 Evaluations | Deterministic evaluations over the local corpus: groundedness, by checking that the documents an answer cites actually support its claims; citation correctness; prompt-injection canaries; latency and token use; all with regression baselines. Relevance scoring and any LLM judge are out of scope. | Phase 9; the Phase 2 retrieval baseline and the version-controlled corpus | Evaluation evidence is reproducible; known failures are tracked; changes are compared with baselines before release. | **Accepted 2026-09-20**: evidence in [`docs/verification/phase-11-evaluations-acceptance.md`](verification/phase-11-evaluations-acceptance.md). Nine of ten cases pass; the one failure is recorded in the record. |
| 12 Observability | OpenTelemetry traces, metrics, logs, correlation, and useful retrieval and citation events across the approved runtime path with sensitive-data redaction. | Phase 9, 11; approved runtime and evaluation signals | Requests can be diagnosed across service boundaries without leaking prompts, documents, tokens, or personal data. | **Planned; post-MVP** |
| 13 CI/CD | A validation pipeline that runs on every push and pull request: Python tests, frontend lint, tests and build, and Terraform format and validate. | Phase 1 Terraform conventions | Changes are validated automatically before merge, a failure names the layer that broke, and the pipeline needs no credentials and holds no write access. | **Accepted 2026-09-20**: evidence in [`docs/verification/phase-13-cicd-acceptance.md`](verification/phase-13-cicd-acceptance.md) |
| 14 Advanced infrastructure hardening | Production reliability, retries, timeouts, idempotent synchronization, backpressure, health checks, recovery, capacity, and controlled failure handling. | Phase 9-13; Phase 1 resource and source conventions | Failure modes, recovery, capacity, and operational runbooks are tested without corrupting source state or weakening governance. | **Retired 2026-09-20.** It is operational maturity for real load — retries, backpressure, capacity and recovery — none of which this project has. See the Work Record. |
| 15 SharePoint as a second source | Deliberately late SharePoint integration: verified connector/API behavior, permissions mapping, synchronization, citations, evaluation coverage, rollout, and rollback. | Phase 14; all applicable security, prompt-injection, evaluation, observability, and delivery evidence | SharePoint content is governed, permission behavior is tested, citations remain trustworthy, and rollout/rollback are documented. | **Retired 2026-09-20.** There is no demand for a second knowledge source, and it was the most expensive remaining item. See the Work Record. |

## Strict Priority

The implementation order is not interchangeable:

1. Complete and accept the Phase 0 foundation contract.
2. Establish the Terraform-managed Azure foundation and Blob-backed knowledge source in Phase 1.
3. Prove retrieval quality and citation correctness in Phase 2, including exact IDs, semantic queries, and multi-document retrieval.
4. Stop and record the hard Phase 2 retrieval acceptance gate.
5. Only then begin Phase 3 Foundry Agent MVP, Phase 4 FastAPI, and Phase 5 Next.js; the MVP completes only when the end-to-end path works.
6. Only after the MVP may the remaining post-MVP phase proceed: Phase 12 observability. Phase 11 evaluations and Phase 13 CI/CD are accepted, and Phases 6, 7, 8, 10, 14 and 15 are retired and are no longer part of the sequence.

Foundry IQ remains the MVP retrieval intelligence layer. Custom retrieval orchestration, ranking, chunking, query routing, or citation assembly is out of scope unless a verified gap is documented and an ADR is accepted.

## Work Record

Phases 0-5 and the MVP are complete; the checklist that tracked them is retired. **MVP complete 2026-09-19**: phases 3, 4 and 5 accepted, with evidence in [`docs/verification/`](verification/). **Post-MVP boundary superseded 2026-09-20**: the project owner selected Phase 9, Security, as the next phase, which was the only authorized post-MVP phase. **Phase 9 accepted 2026-09-20**: evidence in [`docs/verification/phase-9-security-acceptance.md`](verification/phase-9-security-acceptance.md).

### Phase 9 scope decisions (2026-09-20)

Phase 9 hardens the surface that already exists. Three items from its original row were trimmed by the project owner, and two phases were retired.

- **Network and data controls — out of scope.** Private endpoints, firewall rules and IP restrictions are infrastructure-hardening work with no place in a portfolio-scale RAG demonstration, and they would break the operator's local development path. Removing them from Phase 9 does **not** mean the resources are network-restricted: the storage account, the search service and the Foundry project keep their default public network access. Nothing in this phase claims otherwise.
- **Data retention — out of scope.** No soft-delete, retention policy or document lifecycle is added. Blob versioning stays enabled, but that is a recovery property, not a retention policy.
- **Audit logging — deferred.** There is no persisted record of who asked what. Agent tracing does record the agent's own runs as spans in the Foundry portal, which partially covers this, but it is not an access audit trail: it carries no caller identity. It is also the Phase 12 exception recorded below, not a Phase 9 control.
- **Phases 7 and 8 — retired.** The agent's only tool is the knowledge base and Foundry Agent Service executes it server side, so neither a local operational-tool framework nor an MCP layer would have a consumer. Retiring them also removed the "operational-tool design from Phase 7" dependency that Phase 9 previously carried.

Two narrow exceptions were explicitly authorized by the project owner before that supersession, and neither opens its phase:

- **Grounding probes** — the four adversarial probes became a repeatable fixture (`tests/fixtures/grounding-probes.yaml`). No scoring and no metrics, so the exception did not open Phase 11.
- **Agent tracing** — a Log Analytics workspace, an Application Insights resource and the connection that links them to the Foundry project. Agent runs are readable in the Foundry portal as spans. No metrics, logs, correlation, alerting or redaction, so Phase 12 stays unstarted.

### Second roadmap trimming (2026-09-20)

The project owner cut the remaining roadmap for the last time. Phases 11, 12 and 13 are the only phases that remain; Phases 6, 10, 14 and 15 were retired here, alongside Phases 7 and 8 which were retired earlier the same day. The reason is consistent: this is a portfolio-scale RAG demonstration, and each retired phase is either expensive, addresses a concern that only matters at a scale this project does not have, or duplicates work Foundry IQ already owns.

- **Phase 6, retrieval optimization — retired.** Foundry IQ owns retrieval, and the only real knob is a knowledge-base setting rather than code. Without a measurement harness an optimization cannot be shown to be an improvement, and that harness is Phase 11.
- **Phase 10, prompt-injection defenses — retired.** The guardrail covers direct injection, and the indirect path is bounded by the agent having one read-only tool. The platform control for retrieved content is not verifiable through this retrieval path.
- **Phase 14, advanced infrastructure hardening — retired.** It is operational maturity for real load — retries, backpressure, capacity and recovery — none of which this project has.
- **Phase 15, SharePoint — retired.** There is no demand for a second knowledge source, and it was the most expensive remaining item.
- **Phases 7 and 8 — already retired.** Recorded in the Phase 9 scope decisions above and unchanged here.

Two items were carried forward rather than dropped with their phases, and both now live in Phase 11:

- **The Phase 6 retrieval experiment.** Compare the retrieval reasoning effort against the grounding probes and keep the cheapest setting that still passes.
- **The Phase 10 injection threat.** A poisoned document must not change an answer, so it is recorded as a Phase 11 evaluation criterion.

### Phase 13 scope and acceptance (2026-09-20)

Phase 13 was trimmed to the one part that applies to this project and accepted on 2026-09-20; the evidence is in [`docs/verification/phase-13-cicd-acceptance.md`](verification/phase-13-cicd-acceptance.md). `.github/workflows/ci.yml` runs on every push and pull request across three jobs — Python tests, frontend lint, tests and build, and Terraform format and validate — and holds no credentials or write access.

Four items from the original row were not applicable, not deferred:

- **Terraform plan gate.** Planning needs the state, and the repository declares no `backend` block, so the state is one git-ignored file on the operator's machine. A CI plan would propose creating every resource from scratch. Declined deliberately: the real prerequisite, moving the state to a remote backend with a federated identity, was judged disproportionate.
- **Artifact provenance.** Nothing is packaged or deployed — no Dockerfile, no compose file, no deployment manifest — so there is no artifact to attest.
- **Environment promotion.** There is one environment, the operator's machine, with nothing to promote between.
- **Controlled deployment approvals.** Nothing is deployed, so an approval gate would guard nothing.

### Phase 11 evaluations (2026-09-20)

Phase 11 was accepted on 2026-09-20; the evidence is in [`docs/verification/phase-11-evaluations-acceptance.md`](verification/phase-11-evaluations-acceptance.md). It was delivered as Tier 1, deterministic evaluation, with no LLM judge and no `azure-ai-evaluation` dependency: for every value an answer asserts, the harness checks whether the document the answer cited actually contains it. That is possible because the corpus is version-controlled and local, so a value that is present only in an uncited document is detectable without a model.

The harness is `tests/run_evaluations.py` with pure checkers in `tests/eval_checks.py`, ten fixture cases in `tests/fixtures/evaluation-cases.yaml`, and 42 unit tests in `tests/test_eval_checks.py`. `tests/run_probes.py` was reduced to a thin wrapper over the shared runner, with its CLI and JSON output unchanged. The baseline committed as `tests/baseline.json` recorded 9 of 10 cases passing, 4 302 ms to 8 584 ms per case, and roughly 61 500 input and 1 270 output tokens across the ten cases.

The one failure, `runbook-index-command`, is a real defect recorded rather than fixed or deleted: the answer is correct and grounded, but it cites two documents that do not contain the index name, which appears only in `runbooks/database-latency.md`. The detail is in the acceptance record. Two experiments the harness enables — the Phase 6 retrieval reasoning-effort comparison and the Phase 10 poisoned-document case — remain unrun because both are operational rather than code.
