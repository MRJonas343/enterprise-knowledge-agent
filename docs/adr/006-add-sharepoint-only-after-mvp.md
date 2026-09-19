# 006: Add SharePoint Only After MVP

## Status

Accepted

## Context

SharePoint is a valuable enterprise source but introduces connector behavior, permissions, freshness, governance, and citation risks. The brief explicitly places it late in the roadmap.

## Decision

Defer SharePoint integration until after the MVP gate and the pre-SharePoint readiness phase. Implement it as the late Phase 15 source only after permission, synchronization, citation, evaluation, rollout, and rollback requirements are defined and verified.

## Alternatives

- Make SharePoint the first source.
- Add SharePoint in parallel with the Blob-backed retrieval milestone.
- Support all enterprise sources before accepting the MVP.

These alternatives increase early integration and governance risk before the core retrieval contract is proven.

## Consequences

Blob Storage remains the primary source through MVP. SharePoint planning may be documented, but implementation and connector dependencies are blocked until the roadmap prerequisites and MVP acceptance are complete.
