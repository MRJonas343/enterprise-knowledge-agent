# Architecture Decision Records

Architecture Decision Records (ADRs) capture durable choices, their scope, and the evidence or assumptions behind them. They prevent agents from re-litigating settled decisions and make deliberate changes reviewable.

## Quick Path

1. Read the relevant ADR before changing an architectural boundary.
2. If the change is durable, add the next number or update the existing decision with a clear reason.
3. Verify current Microsoft documentation for Azure/Foundry behavior and record versions or preview assumptions.
4. Update the roadmap and architecture index when sequencing or boundaries change.

## Required Format

Every ADR must contain:

```markdown
# NNN: Decision title

## Status
Accepted | Planned | Superseded | Rejected

## Context
What problem, constraint, or product intent requires a decision?

## Decision
What is being chosen, and what boundary does it establish?

## Alternatives
What credible alternatives were considered and why were they not selected?

## Consequences
What benefits, costs, risks, follow-up work, and verification obligations result?
```

Do not invent implementation details in a stub. Mark unverified or preview-dependent choices as Planned and add the verification obligation to Consequences.

## Initial Decisions

| ADR | Decision | Status |
| --- | --- | --- |
| [001](001-use-foundry-iq.md) | Use Foundry IQ as the primary retrieval intelligence layer | Accepted |
| [002](002-use-blob-storage-as-primary-knowledge-source.md) | Use Blob Storage as the primary knowledge source | Accepted |
| [003](003-use-terraform-from-day-one.md) | Use Terraform from day one | Accepted |
| [004](004-use-fastapi-as-application-gateway.md) | Use FastAPI as the application gateway | Accepted 2026-09-19 |
| [005](005-use-mcp-for-runtime-tools.md) | Use MCP for governed runtime tools | Rejected 2026-09-20 |
| [006](006-add-sharepoint-only-after-mvp.md) | Add SharePoint only after MVP | Rejected 2026-09-20 |
