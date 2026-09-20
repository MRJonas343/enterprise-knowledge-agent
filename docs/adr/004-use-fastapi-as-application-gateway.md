# 004: Use FastAPI as the Application Gateway

## Status

Accepted 2026-09-19

## Context

The target technology stack names Python/FastAPI as the application gateway between the user-facing client and the approved agent/runtime path.

Phase 3 acceptance verified the agent, and the Phase 3 record carries two contract inputs forward: citation annotations resolve to a source URL and a text span but carry no human-readable title, and the terminal client does not resolve citation markers, leaving `【N:M†source】` unreadable to a user.

## Decision

Use FastAPI as the application gateway. The gateway exposes the approved agent path, resolves citations into the response contract, and maps agent and service failures to HTTP status codes.

Two constraints follow from the Phase 3 evidence:

- The API must not assume a human-readable citation title exists, because `title` duplicates the URL.
- The API must expose citations as structured data, so a client never has to show an unresolvable marker.

## Alternatives

- Expose the agent service directly to the frontend.
- Use another Python web framework.
- Use an Azure-managed API surface without an application gateway.

## Consequences

FastAPI needs explicit contracts, error mapping, citation preservation, and tests. The conversation identifier returned by the API is not an authorization boundary: it is application state, and end-user authorization is a later security phase.
