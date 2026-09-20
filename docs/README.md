# Documentation Index

This directory is the working map for the Enterprise Knowledge Agent. Phase 1 infrastructure, the knowledge corpus, the retrieval path and the Foundry agent are implemented, and both the Phase 2 retrieval gate and the Phase 3 agent gate are recorded in [`verification/`](verification/).

## Quick Path

| Need | Start here |
| --- | --- |
| Know what may be implemented now | [`../AGENTS.md`](../AGENTS.md) |
| Find the active phase and gate | [`development-roadmap.md`](development-roadmap.md) |
| Understand the product and target system | [`project-context.md`](project-context.md) |
| Follow the agent workflow | [`agent-guidelines.md`](agent-guidelines.md) |
| Review architecture boundaries | [`architecture/README.md`](architecture/README.md) |
| Review or add a decision | [`adr/README.md`](adr/README.md) |
| Create or validate a diagram | [`diagrams/README.md`](diagrams/README.md) |
| Read the recorded gate evidence | [`verification/`](verification/) |

## Current Status

| Phase | Status |
| --- | --- |
| Phase 0 Foundation | Accepted |
| Phase 1 Infrastructure + knowledge source | Accepted |
| Phase 2 Retrieval | **Accepted 2026-09-19** |
| Phase 3 Foundry agent | **Accepted 2026-09-19** |
| Phases 4-5 FastAPI and Next.js | Not started |

The MVP completes when the end-to-end agent, API and UI path works, so Phases 4 and 5 remain. Evaluations, observability, security hardening, prompt-injection defenses and SharePoint stay in later phases.

Read the recorded evidence in [`verification/phase-2-retrieval-acceptance.md`](verification/phase-2-retrieval-acceptance.md) and [`verification/phase-3-agent-acceptance.md`](verification/phase-3-agent-acceptance.md).

## Reading Order

1. [`../AGENTS.md`](../AGENTS.md) for the operational contract.
2. [`development-roadmap.md`](development-roadmap.md) for phase ownership and dependencies.
3. [`agent-guidelines.md`](agent-guidelines.md) for implementation and verification rules.
4. [`project-context.md`](project-context.md) for durable product context.
5. [`architecture/README.md`](architecture/README.md) and relevant ADRs for system boundaries.

## Document Status

| Document | Purpose | Status |
| --- | --- | --- |
| `development-roadmap.md` | Phase 0-15 sequence and gates | Maintained plan |
| `agent-guidelines.md` | Agent operating rules | Maintained contract |
| `project-context.md` | Durable product brief | Product intent and target context |
| `architecture/README.md` | Target and MVP data path | Target architecture; implementation is future work |
| `adr/` | Durable decisions and assumptions | Initial decisions documented |
| `verification/` | Dated gate acceptance records | Phases 2 and 3 accepted 2026-09-19 |
| `diagrams/` | Diagram evidence and ownership rules | Index only |

## Contribution Rule

Documentation changes must preserve the Phase 2 gate, identify assumptions about preview/evolving Foundry APIs, and avoid presenting planned components as implemented. Add an ADR when a change is architectural or changes an approved boundary.
