# 004: Use FastAPI as the Application Gateway

## Status

Planned

## Context

The target technology stack names Python/FastAPI as the application gateway between the user-facing client and the approved agent/runtime path.

## Decision

Plan to use FastAPI as the application gateway after the Phase 2 retrieval acceptance and subsequent Foundry Agent Service boundary are proven.

## Alternatives

- Expose the agent service directly to the frontend.
- Use another Python web framework.
- Use an Azure-managed API surface without an application gateway.

## Consequences

FastAPI will need explicit contracts, error mapping, citation preservation, and tests in a later phase. No FastAPI implementation is authorized in the current Phase 0-2 boundary.
