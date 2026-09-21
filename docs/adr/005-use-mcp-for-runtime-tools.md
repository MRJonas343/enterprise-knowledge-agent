# 005: Use MCP for Governed Runtime Tools

## Status

Rejected 2026-09-20

## Context

The target brief includes MCP for standardized runtime-tool connectivity, while the initial milestone is retrieval-only.

## Decision

Plan to use MCP for explicitly approved, schema-validated runtime tools after the retrieval and agent boundaries are accepted. MCP will not replace Foundry IQ retrieval.

## Alternatives

- Embed ad hoc tool calls directly in application code.
- Provide unrestricted plugins or arbitrary code execution.
- Exclude runtime tools entirely.

## Consequences

Tool schemas, authorization, timeouts, auditability, and negative tests must be designed in a later phase. The Phase 2 retrieval acceptance this decision was conditioned on is complete (2026-09-19); MCP runtime tools remain post-MVP and are not yet authorized. Retired 2026-09-20: the agent's only tool is the knowledge base, executed server side by Foundry Agent Service, so neither runtime tools nor an MCP layer would have a consumer. This decision is not being pursued.
