# 002: Use Blob Storage as the Primary Knowledge Source

## Status

Accepted

## Context

The first milestone needs a small, reproducible, version-controlled source that can be synchronized to Azure and validated through Foundry IQ.

## Decision

Use version-controlled Markdown synchronized to Azure Blob Storage as the primary Phase 2 knowledge source and the initial MVP source path.

## Alternatives

- Start with SharePoint.
- Start with direct application-managed document storage.
- Start with multiple enterprise connectors.

These alternatives are deferred because they add governance, permissions, or integration complexity before the retrieval contract is proven.

## Consequences

The source-of-truth workflow is repository Markdown plus deterministic synchronization. Blob-backed Foundry IQ retrieval and citations must be validated before another source is introduced. Document lifecycle and richer metadata remain later work.
