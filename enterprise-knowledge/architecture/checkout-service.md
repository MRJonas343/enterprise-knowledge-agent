# Checkout Service

| Field | Value |
| --- | --- |
| Document ID | ARCH-CHK-001 |
| Document type | architecture |
| Service | checkout-api |
| Team | checkout |
| Classification | internal |
| Last updated | 2026-06-12 |

## Purpose

checkout-api is the synchronous orchestration entry point for the Aurora Commerce purchase flow. It is owned by the checkout team, runs on AKS in its own namespace, and is deliberately stateless: it holds no database and no cache of its own. Every piece of durable state it needs is owned by a downstream service.

Because checkout-api is stateless it is easy to scale horizontally, but it is also the most exposed service on the platform: it fans out to three downstream services and inherits their latency. Its place among the other five services is mapped in `architecture/system-overview.md`.

## Responsibilities

- Accept and validate incoming checkout requests from partner clients.
- Reserve stock by calling inventory-service.
- Authorize payment by calling payment-service.
- Create the order record by calling order-service.
- Return a single checkout result to the caller.

checkout-api does not own order state, stock state or payment state. It coordinates, then hands ownership to the downstream service.

## Dependencies

| Dependency | Call style | Timeout | Notes |
| --- | --- | --- | --- |
| payment-service | Synchronous HTTPS | 2 seconds | No circuit breaker |
| inventory-service | Synchronous HTTPS | 2 seconds | Stock reservation |
| order-service | Synchronous HTTPS | 2 seconds | Order creation |
| authentication-service | Synchronous, via ingress | n/a | Bearer token validation |
| Application Insights | Telemetry | n/a | Request and dependency telemetry |

## Interfaces

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/v1/checkout` | POST | Execute the checkout orchestration |
| `/v1/checkout/{id}/status` | GET | Read a previously returned checkout status |
| `/healthz` | GET | Liveness and readiness probe |

## Orchestration sequence

1. Validate the request body and the bearer token.
2. Call inventory-service `POST /v1/reservations` to hold stock.
3. Call payment-service `POST /v1/payments/authorize` to authorize payment.
4. Call order-service `POST /v1/orders` to persist the order.
5. Release the stock hold if the order write fails.
6. Return the checkout result.

## The payment dependency is the weak point

The call from checkout-api to payment-service is **synchronous over HTTPS with a 2 second timeout and no circuit breaker**. This is the defining architectural risk of checkout-api.

When payment-service is slow, checkout-api threads block for up to 2 seconds each. Under load, blocked threads exhaust the request pool, p95 latency rises sharply and the error rate climbs. There is no circuit breaker to shed load, so a degraded payment-service degrades checkout-api for as long as the degradation lasts.

The April 2026 latency incident demonstrated this exactly. payment-service v2.31.0 introduced a long-running reporting query that exhausted the PostgreSQL connection pool; checkout-api p95 latency rose to 840 ms and the error rate reached 6%. The root cause and response are documented in `incidents/INC-2026-002.md`. The diagnosis path is in `runbooks/database-latency.md`, and the corrective action was a rollback to payment-service v2.30.4 following `engineering/rollback-procedure.md`.

## Data model

checkout-api stores no durable data. It forwards the request payload to order-service, which owns order state in the `orders` PostgreSQL database. checkout-api may cache nothing between requests; if a downstream call is retried, the client and the idempotency key are the only carriers of continuity.

## Failure modes

| Failure | Observable symptom | Response |
| --- | --- | --- |
| payment-service slow or unavailable | checkout p95 above 400 ms SLO, 5xx rising | Check payment-service pool and CPU; see `runbooks/database-latency.md` |
| inventory-service reservation timeouts | Checkout failures before payment | Escalate to the catalog team |
| order-service write failures | Payment authorized but no order | Compensate and release the stock hold |
| authentication-service token failures | Burst of HTTP 401 | See `runbooks/redis-failure.md` |

Because there is no circuit breaker, the first line of defence is to restore payment-service health rather than to protect checkout-api in isolation. If the cause is a payment-service deployment, roll back. See `engineering/rollback-procedure.md`.

## Operational notes

- SLO: p95 latency under 400 ms, error rate under 0.5%.
- Current version: checkout-api v3.7.2. This version is not implicated in any recorded incident.
- checkout-api is safe and cheap to restart: it is stateless, and in-flight checkouts fail cleanly rather than corrupting state.
- A circuit breaker on the payment-service client is a known, still-open improvement. Until it ships, the synchronous edge remains the dominant risk.
- Release, canary and change-approval rules for checkout-api are defined in `engineering/deployment-guidelines.md`.

## Idempotency and compensation

checkout-api must be safe to retry because the payment leg is synchronous and bounded by a 2 second timeout:

- Every checkout carries a client-supplied idempotency key.
- payment-service deduplicates authorization attempts by that key.
- order-service deduplicates order creation by the same key.
- If order creation fails after payment authorization, checkout-api voids the authorization and releases the stock hold.

A timeout does not mean the downstream call failed. checkout-api treats a payment timeout as an unknown outcome and resolves it by querying payment status before retrying. This avoids a double authorization when the first call actually succeeded but responded too slowly.

## Scaling and capacity

- checkout-api scales horizontally and holds no state, so scaling out is the fastest capacity lever.
- Each checkout ties up a request thread while it waits on payment-service; the 2 second timeout bounds how long that thread is unavailable.
- Because there is no circuit breaker, scaling checkout-api cannot protect it from a slow payment-service; it only delays the point at which threads are exhausted.
- Run at least 3 replicas so a single-node disruption cannot remove the service.
- The service is safe to restart at any time: in-flight checkouts fail cleanly and no state is corrupted.

## Related documents

architecture/payment-service.md
architecture/system-overview.md
runbooks/database-latency.md
engineering/rollback-procedure.md
engineering/deployment-guidelines.md
incidents/INC-2026-002.md
