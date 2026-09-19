# 001: Use Foundry IQ for Primary Retrieval

## Status

Accepted

## Context

The product requires grounded enterprise answers with citations. The brief establishes Foundry IQ as the primary retrieval intelligence layer for the MVP and the first milestone.

## Decision

Use Foundry IQ and its Knowledge Base abstraction as the primary retrieval intelligence layer. The MVP will not build custom retrieval orchestration around it.

## Alternatives

- Build custom retrieval orchestration with direct Azure AI Search calls.
- Use another managed retrieval abstraction.

These alternatives are not selected for the MVP because they would weaken the stated Foundry IQ boundary and duplicate retrieval responsibilities.

## Consequences

The Blob-backed Knowledge Base path is the Phase 2 acceptance target. Foundry IQ and Foundry APIs may be preview or evolving; implementation must verify current Microsoft documentation, versions, and supported behavior before relying on them. Any verified gap requires a new ADR rather than an implicit parallel retrieval layer.
