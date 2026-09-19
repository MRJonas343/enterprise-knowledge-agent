# Diagrams

Diagrams explain architecture, workflows, data paths, sequences, and lifecycle states. They belong here when they describe repository or system behavior and should remain readable without a separate presentation tool.

## Placement

- Keep architecture and MVP data-path diagrams in [`../architecture/README.md`](../architecture/README.md) when a small Mermaid diagram is sufficient.
- Add larger diagrams under this directory with a descriptive filename, such as `mvp-retrieval-flow.md` or `agent-request-sequence.md`.
- Link every diagram from the relevant architecture, roadmap, or ADR page.

## Evidence Requirements

Every non-trivial diagram must state:

- Scope and phase.
- Implemented, verified, preview/evolving, and planned components.
- Source documents, ADRs, code, Terraform, or service evidence used.
- Date of verification and version/API assumptions where applicable.
- Any intentionally omitted or simplified boundary.

Do not draw planned components as if they were live. Do not include secrets, private endpoints, personal data, or absolute local paths. Update diagrams when the implementation or accepted architecture changes.

## Review Checklist

- [ ] The diagram has one clear question or path.
- [ ] Arrows and labels match the written architecture.
- [ ] Phase and status labels are visible.
- [ ] Foundry IQ remains the primary MVP retrieval intelligence layer.
- [ ] SharePoint is not shown as an MVP dependency.
- [ ] Preview/evolving Azure capabilities are marked for current documentation verification.
- [ ] Evidence links and assumptions are recorded.
