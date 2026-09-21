# 006: Add SharePoint Only After MVP

## Status

Rejected 2026-09-20

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

Retired 2026-09-20: Phase 15 was retired when the remaining roadmap was reduced to evaluations, observability and CI/CD. SharePoint is not being added, so this deferral is never exercised. The decision it rests on still stands — Blob Storage is the primary source, and the alternatives below stay rejected.
