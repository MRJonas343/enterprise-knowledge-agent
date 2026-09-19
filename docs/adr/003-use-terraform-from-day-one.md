# 003: Use Terraform from Day One

## Status

Accepted

## Context

The Azure environment must be reproducible and reviewable from the beginning rather than reconstructed after manual setup.

## Decision

Use Terraform as the infrastructure source of truth from Phase 1 onward.

## Alternatives

- Create resources manually in the Azure portal first.
- Use ad hoc CLI scripts and add Terraform later.
- Use another infrastructure-as-code tool.

These alternatives do not satisfy the stated day-one reproducibility requirement.

## Consequences

Provider versions, inputs, state handling, manual prerequisites, and environment assumptions must be documented. Credentials and sensitive state must remain outside committed files. Exact resource and provider details are implementation work and require current Azure documentation verification.
