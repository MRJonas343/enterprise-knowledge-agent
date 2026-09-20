# Agent Guidelines

These rules make work reproducible, reviewable, and safe. They apply to agents and contributors working in this repository.

## Start Here

1. Read [`../AGENTS.md`](../AGENTS.md).
2. Identify the active phase in [`development-roadmap.md`](development-roadmap.md).
3. Read the relevant sections of [`project-context.md`](project-context.md), [`architecture/README.md`](architecture/README.md), and related ADRs.
4. Check current official Microsoft documentation before relying on an Azure, Foundry, SDK, provider, or API behavior.
5. State the intended change, phase gate, assumptions, and verification evidence before editing.

## Decision Rules

| Question | Rule |
| --- | --- |
| Is this in the active phase? | If no, document it as future work and do not implement it. |
| Does it change a durable boundary? | Add or update an ADR before implementation. |
| Is the Foundry capability preview or evolving? | Verify current Microsoft docs, record date/version/assumptions, and avoid undocumented contracts. |
| Does it duplicate Foundry IQ retrieval? | Do not add it to the MVP; document the verified gap and obtain an accepted ADR first. |
| Does it need a secret or sensitive document? | Use an approved secret mechanism and sanitized fixture; never commit or print the value. |
| Is acceptance based only on a non-empty answer? | It is insufficient; require source identity and citations. |

## Phase Discipline

Phases 0-5 are accepted and the MVP is complete: the infrastructure, the knowledge source, cited retrieval, the Foundry agent, the FastAPI gateway and the Next.js frontend are implemented, with evidence in [`verification/`](verification/). Post-MVP work (phases 6-15) must not start until the current boundary is explicitly superseded. It is acceptable to document post-MVP interfaces and dependencies as planned, but not to create placeholders that imply implementation.

Phase 2 was accepted once the same known Markdown source could be traced through version control, Blob Storage, the Blob-backed Foundry IQ Knowledge Base, and a cited retrieval result.

## Azure Boundary Rules

- Verify provider versions, API versions, regional availability, preview labels, quotas, and current CLI/SDK syntax against official Microsoft documentation.
- Record every non-obvious assumption in the roadmap, an ADR, or a phase verification note.
- Do not mix manual portal changes into a reproducibility claim. If a manual prerequisite is unavoidable, document it explicitly and track its removal.

## Validation Expectations

Validation must match the phase:

- Documentation: inspect links, headings, status labels, phase ordering, contradictions, and secret patterns.
- Terraform: run formatting and validation, inspect the plan, and prove a clean reproducible path without exposing state secrets.
- Source synchronization: verify deterministic paths, content identity, update behavior, and no accidental files.
- Foundry IQ retrieval: verify the Knowledge Base uses Blob content, answer grounding, citation source identity, and expected failure for missing/unsupported content.
- Runtime phases: add contract, integration, negative, and regression tests appropriate to the service boundary.

Do not call an unverified preview response, mock, or local-only result a phase acceptance. Preserve command, version, environment class, date, and result in the verification record without storing credentials.

## Cost and Reproducibility

- Prefer small fixtures and bounded test queries.
- Avoid repeated remote indexing, deployment, or evaluation runs when a local structural check answers the question.
- Record paid-resource assumptions, expected request/indexing costs, quotas, and cleanup steps before remote validation.
- Pin dependencies and use lock files once code exists.
- Make synchronization and validation rerunnable; avoid one-time portal configuration.
- Never delete or recreate shared resources to make a test pass without explicit authorization and a documented impact.

## Credentials and Sensitive Data

- Never commit API keys, access tokens, passwords, connection strings, certificates, Terraform state, or copied cloud responses containing secrets.
- Use environment injection or an approved secret manager. Keep examples redacted and clearly synthetic.
- Do not include absolute local paths, usernames, hostnames, tenant IDs, private endpoints, or confidential document content in committed docs.
- Redact prompts, citations, traces, screenshots, and evaluation output when they may contain enterprise data.
- If a secret is exposed, stop using it, report the exposure, rotate it through the owner-approved process, and document only the sanitized incident.

## Documentation and ADR Workflow

For a documentation change, update the smallest complete set of linked pages and keep current status explicit. For a durable decision:

1. Add or update one numbered ADR in [`adr/README.md`](adr/README.md).
2. Use the required sections: Context, Decision, Alternatives, Consequences, and Status.
3. Cite official documentation and version assumptions when the decision depends on an Azure or Foundry capability.
4. Update the roadmap or architecture index if the decision changes sequencing or boundaries.
5. Run link and consistency checks before handoff.

## Handoff Checklist

- [ ] Phase and gate are named.
- [ ] Scope excludes later phases where required.
- [ ] Official docs and versions were checked.
- [ ] Secrets and sensitive data are absent.
- [ ] Validation commands and results are recorded.
- [ ] Roadmap, ADRs, architecture, and diagrams remain consistent.
- [ ] Next owner and next gate are unambiguous.
