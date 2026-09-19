# Project Context

## Purpose

The Enterprise Knowledge Agent is intended to answer enterprise questions with grounded, traceable evidence from governed organizational knowledge. The first usable proof is deliberately narrow: retrieve from Markdown stored in Blob Storage through a Blob-backed Foundry IQ Knowledge Base and return citations that identify the source.

The repository currently has no application code or infrastructure. This page describes product intent and target boundaries, not implemented behavior.

## Personas and Use Cases

| Persona | Need | Evidence of value |
| --- | --- | --- |
| Software Engineer | Troubleshoot a service or system using approved engineering knowledge | A concise answer with inspectable citations, exact source identity, and clear uncertainty |
| SRE/DevOps Engineer | Correlate runbooks, service context, incidents, and operational guidance | A traceable multi-source answer that distinguishes evidence from missing context |
| Engineering Lead | Understand recurring issues, ownership, and the reliability implications of proposed guidance | Cross-source evidence, explicit limitations, and governance-aware recommendations |
| Knowledge owner | Publish and maintain authoritative content | Versioned source workflow and auditable updates |
| Platform/operator owner | Run a reproducible, observable, cost-aware service | Terraform-managed environments, diagnostics, and runbooks |
| Security/governance owner | Control access and data handling | Explicit boundaries, redaction, permissions, and evidence |

The core target use case is multi-source troubleshooting: a Software Engineer or SRE/DevOps Engineer asks a question that requires correlating an approved runbook, service documentation, incident or change context, and other governed operational knowledge. The intended answer identifies which sources support it, preserves exact source identity, and states when the available evidence is insufficient. This is a target product scenario, not an implemented capability in the current repository.

Initial implementation remains read-oriented knowledge retrieval and grounded answers over the Phase 1 Blob source. Actions, autonomous changes, unrestricted enterprise search, and broad multi-source ingestion are non-goals for the initial retrieval milestone.

## Portfolio Relationship

CloudOpsAgent and the Enterprise Knowledge Agent are complementary portfolio projects, not duplicate implementations. CloudOpsAgent focuses on AWS Bedrock and LangGraph operational orchestration. This project focuses on Azure/Foundry enterprise Agentic RAG over governed organizational knowledge. They may share concerns such as operator safety, governance, and observability, but this repository does not recreate CloudOpsAgent or claim shared runtime components.

## Target Architecture

The target system uses Microsoft Foundry services and Azure primitives with a thin application surface:

- Foundry IQ is the primary retrieval intelligence layer and Knowledge Base abstraction.
- Azure Blob Storage is the primary Phase 2 knowledge source.
- Terraform manages Azure infrastructure and reproducible environment configuration.
- Foundry Agent Service is the planned agent/orchestration surface after retrieval acceptance.
- FastAPI is the planned application gateway after the agent boundary is proven.
- Next.js and TypeScript are the planned user interface.
- MCP is a planned, explicitly governed runtime-tool boundary, not an MVP retrieval replacement.
- OpenTelemetry is the planned cross-service observability approach.
- Evaluation workflows are planned for groundedness, relevance, citation quality, cost, and latency.
- SharePoint is intentionally late and follows MVP plus governance readiness.

Preview or evolving Azure capabilities, especially Foundry IQ and Foundry APIs, must be checked against current Microsoft documentation and recorded with versions and assumptions before implementation.

## Technology Roles

These roles describe the intended portfolio and product boundaries; they do not claim that any component is implemented.

| Technology or boundary | Intended role | Roadmap position |
| --- | --- | --- |
| Terraform and Azure | Reproducible infrastructure, naming, environment configuration, and authentication foundation | Phase 0-1 |
| Blob Storage and AI Search | Governed primary knowledge-source foundation for initial enterprise documents | Phase 1 |
| Foundry IQ Knowledge Source and Knowledge Base | MVP retrieval intelligence, grounding, and citation path over the Blob source | Phase 1-2 |
| Foundry Agent Service | Agent interaction and conversation boundary after retrieval acceptance | Phase 3 |
| FastAPI | Application API boundary between the agent path and clients | Phase 4 |
| Next.js and TypeScript | User-facing question-and-answer experience and citation inspection | Phase 5; completes the MVP path |
| Dynamic tools and MCP | Explicitly governed operational actions and interoperability, separate from retrieval | Phases 7-8, post-MVP |
| Security and prompt-injection defenses | Authorization, data protection, safe agent/tool behavior, and threat mitigation | Phases 9-10, post-MVP |
| Evaluations and OpenTelemetry | Quality evidence, regression detection, diagnosis, and operational visibility | Phases 11-12, post-MVP |
| CI/CD and infrastructure hardening | Controlled delivery, reliability, recovery, capacity, and production operations | Phases 13-14, post-MVP |
| SharePoint | Deliberately late second knowledge source after governance and rollback readiness | Phase 15 |

## Knowledge Model

The initial knowledge unit is a version-controlled Markdown document. Its meaningful identity includes repository path/version, synchronized Blob object, and the citation returned by Foundry IQ. Later metadata may include owner, effective date, lifecycle state, classification, freshness, and source system, but those fields are future design work unless verified and accepted.

The source-of-truth path is:

`version-controlled Markdown -> deterministic Blob synchronization -> Blob-backed Foundry IQ Knowledge Base -> grounded answer with citations`

This path is the Phase 2 acceptance contract. The MVP must not construct a parallel custom retrieval pipeline around it.

The later multi-source troubleshooting scenario must extend this governed path without weakening source identity, authorization, citations, or the distinction between retrieved evidence and inference. It remains a post-acceptance product direction until the relevant roadmap phases and evidence are complete.

## Error Model

Errors should be explicit and distinguishable rather than converted into confident prose:

- No relevant source: state that the approved knowledge does not support an answer.
- Citation or grounding failure: do not present the result as accepted retrieval.
- Source synchronization failure: preserve the last known good state and report the failed update.
- Foundry/Azure service failure: expose a safe operational error and correlation information without secrets.
- Invalid input or unsupported content: reject predictably and explain the supported boundary.
- Authorization or policy failure: deny safely without revealing protected content.

Detailed runtime error contracts are future work and must be defined in the relevant phase and ADR.

## Testing and Evaluation Direction

Phase 2 validation is retrieval-focused: source identity, synchronization correctness, groundedness, citation presence, and expected failures. Later evaluation should add representative question sets, relevance and citation correctness, groundedness, latency, cost, regression tracking, and adversarial/security cases. Evaluation fixtures must be synthetic or authorized, versioned, reproducible, and scrubbed of secrets and personal data.

## Non-Goals

- No custom retrieval orchestration in the MVP.
- No Foundry Agent Service implementation before Phase 2 acceptance.
- No FastAPI application code or Next.js frontend in this bootstrap.
- No MCP tools, action-taking workflows, or autonomous enterprise changes in the initial retrieval milestone.
- No SharePoint integration before MVP and late-source readiness.
- No claim that preview/evolving Foundry APIs are stable without current documentation verification.
- No unmanaged Azure resources, hard-coded credentials, or portal-only reproducibility.
- No root README, LICENSE, application source, Terraform modules, or placeholder runtime code in this task.
