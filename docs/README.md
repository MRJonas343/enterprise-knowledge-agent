# Documentation Index

This directory is the working map for the Enterprise Knowledge Agent. The infrastructure, the knowledge corpus, the retrieval path, the Foundry agent, the API gateway and the Next.js frontend are implemented, and the Phase 2, 3, 4, 5, 9 and 13 gates are recorded in [`verification/`](verification/).

## Quick Path

| Need | Start here |
| --- | --- |
| Know what may be implemented now | [`../AGENTS.md`](../AGENTS.md) |
| Find the active phase and gate | [`development-roadmap.md`](development-roadmap.md) |
| Understand the product and architecture | [`project-context.md`](project-context.md) |
| Follow the agent workflow | [`agent-guidelines.md`](agent-guidelines.md) |
| Review architecture boundaries | [`architecture/README.md`](architecture/README.md) |
| Review or add a decision | [`adr/README.md`](adr/README.md) |
| Create or validate a diagram | [`diagrams/README.md`](diagrams/README.md) |
| Read the recorded gate evidence | [`verification/`](verification/) |

## Current Status

Phases 0-9 and Phase 13 are accepted and the MVP is complete. The MVP gates cleared on 2026-09-19 and **Phase 9, Security**, was accepted on 2026-09-20; **Phase 13, CI/CD**, was accepted the same day. Phases 11 and 12 (evaluations and observability) remain unstarted; Phases 6, 7, 8, 10, 14 and 15 are retired. [`development-roadmap.md`](development-roadmap.md) is the canonical phase status, and [`verification/`](verification/) holds the dated gate evidence.

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
| `architecture/README.md` | Architecture index and MVP data path | Maintained; path implemented and accepted |
| `adr/` | Durable decisions and assumptions | Initial decisions documented |
| `verification/` | Dated gate acceptance records | Phases 2, 3, 4 and 5 accepted 2026-09-19; Phases 9 and 13 accepted 2026-09-20 |
| `diagrams/` | Diagram evidence and ownership rules | Index only |

## Contribution Rule

Documentation changes must keep the accepted gates intact, identify assumptions about preview/evolving Foundry APIs, and avoid presenting planned components as implemented. Add an ADR when a change is architectural or changes an approved boundary.
