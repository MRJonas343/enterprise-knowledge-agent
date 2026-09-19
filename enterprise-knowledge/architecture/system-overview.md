# System Overview

| Field | Value |
| --- | --- |
| Document ID | ARCH-SYS-001 |
| Document type | architecture |
| Service | platform-wide |
| Team | platform |
| Classification | internal |
| Last updated | 2026-07-15 |

## Purpose

This document is the entry point for the Aurora Commerce platform. It lists the six core services, the shared Azure infrastructure they run on, the request path from the public internet to the workloads, and the cross-service dependencies that determine how failures propagate. Aurora Commerce is a B2B e-commerce SaaS company; the platform runs on Microsoft Azure and is owned jointly by the checkout, payments, orders, catalog, identity and platform teams.

Every other architecture document in this repository refines one service described here. Start here, then read the service document that matches your question.

## Platform context

Aurora Commerce exposes a public storefront and a partner API. All inbound traffic terminates at Azure Front Door, passes through Application Gateway with a Web Application Firewall (WAF), and then reaches the Azure Kubernetes Service (AKS) ingress. Workloads are stateless wherever possible; durable state lives in managed Azure data services.

The platform is deliberately small: six services, three PostgreSQL databases, one Redis cache and two Service Bus topics. This keeps the failure surface understandable and the ownership boundaries clear.

## Services

| Service | Team | Runtime | Primary datastore | Notes |
| --- | --- | --- | --- | --- |
| checkout-api | checkout | AKS | none (stateless orchestrator) | Calls payment-service synchronously over HTTPS with a 2 second timeout. No circuit breaker. Calls inventory-service and order-service. |
| payment-service | payments | AKS | PostgreSQL "payments" database via PgBouncer | Connection pool size 50 per pod. Integrates with NorthPay. |
| order-service | orders | AKS | PostgreSQL "orders" database | Owns order lifecycle state. |
| inventory-service | catalog | AKS | PostgreSQL "catalog" database plus a Redis cache | Stock reservations. |
| authentication-service | identity | AKS | Azure Cache for Redis (sessions, refresh tokens) | Issues OIDC/JWT access tokens. Access token TTL 15 minutes. Refresh token TTL 30 days. |
| notification-service | platform | AKS | none | Consumes Azure Service Bus topics asynchronously. |

## Shared infrastructure

- **Azure Kubernetes Service (AKS)** hosts every service, with one Kubernetes namespace per service.
- **Azure Database for PostgreSQL Flexible Server** provides separate databases for payments, orders and catalog.
- **Azure Cache for Redis, Standard C1** is shared by authentication-service (sessions) and inventory-service (cache).
- **Azure Service Bus** carries the topics `order-events` and `payment-events`.
- **Azure Key Vault**, instance `kv-aurora-prod`, stores all application secrets.
- **Application Insights and Azure Monitor** provide traces, metrics and alerting.
- **Azure Front Door** sits in front of Application Gateway with WAF, then the AKS ingress.
- **Azure Blob Storage** stores reports and exports.

## Request path

1. A client calls the Aurora Commerce partner API on the Front Door endpoint.
2. Front Door terminates TLS and forwards to Application Gateway, where the WAF inspects the request.
3. Application Gateway forwards to the AKS ingress controller.
4. The ingress routes by host and path to the target service namespace.
5. authentication-service validates the bearer token before checkout-api accepts a write request.

Because authentication-service is on the critical path for every authenticated request, its Redis dependency is a platform-wide availability concern. See `architecture/authentication-service.md`.

## Dependencies

The dependency graph is intentionally shallow but not acyclic at the request level:

- checkout-api depends on payment-service, inventory-service and order-service.
- payment-service depends on the `payments` PostgreSQL database through PgBouncer and on NorthPay.
- order-service depends on the `orders` database and publishes to `order-events`.
- inventory-service depends on the `catalog` database and the shared Redis cache.
- authentication-service depends on the shared Redis cache and Azure Key Vault.
- notification-service depends on `order-events` and `payment-events`.

The most fragile edge is checkout-api to payment-service, because it is synchronous, has a fixed 2 second timeout and has no circuit breaker. A degraded payment-service therefore degrades checkout-api directly. See `architecture/checkout-service.md` and `architecture/payment-service.md`.

## Interfaces

| Interface | Type | Consumer | Provider | Notes |
| --- | --- | --- | --- | --- |
| `POST /v1/checkout` | HTTPS | partner clients | checkout-api | Synchronous orchestration entry point |
| `POST /v1/payments/authorize` | HTTPS | checkout-api | payment-service | 2 second client timeout, no circuit breaker |
| `POST /v1/reservations` | HTTPS | checkout-api | inventory-service | Stock reservation hold |
| `POST /v1/orders` | HTTPS | checkout-api | order-service | Creates the order record |
| OIDC discovery and token endpoint | HTTPS | all services | authentication-service | Issues JWT access tokens |
| `payment-events` | Service Bus topic | notification-service | payment-service | Asynchronous payment lifecycle events |

## Data model overview

State is partitioned by service ownership and never shared through a single database:

- **payments** database: payment attempts, authorization records, NorthPay references and settlement status.
- **orders** database: orders, order lines and order state transitions.
- **catalog** database: products, stock levels and reservations; Redis caches hot stock reads.
- **Redis (shared)**: authentication sessions and refresh tokens, plus the inventory cache.

No service reads another service's database directly. All cross-service data access goes through the HTTPS interfaces listed above or through Service Bus events.

## Failure modes

| Failure | Blast radius | Mitigation | Reference |
| --- | --- | --- | --- |
| PostgreSQL connection pool exhaustion | payment-service, then checkout-api | Pool monitoring and rollback | `runbooks/database-latency.md` |
| Payment-service pod CPU saturation | payment-service, then checkout-api | Retry budget and circuit breaker | `runbooks/high-cpu.md` |
| Redis primary failover | authentication-service, all authenticated calls | Failover handling and session rebuild | `runbooks/redis-failure.md` |
| NorthPay API degradation | payment-service | Circuit breaker on the NorthPay client | `runbooks/high-cpu.md` |

## Operational notes

Service level objectives:

| Service | p95 latency | Error rate |
| --- | --- | --- |
| checkout-api | under 400 ms | under 0.5% |
| payment-service | under 600 ms | — |
| authentication-service | under 250 ms | — |

Telemetry from every service lands in Application Insights. Azure Monitor evaluates the SLOs above and drives the alert thresholds documented in the runbooks. A new deployment that breaches an SLO is a rollback candidate; follow `engineering/rollback-procedure.md`.

## Related documents

architecture/payment-service.md
architecture/checkout-service.md
architecture/authentication-service.md
runbooks/database-latency.md
runbooks/high-cpu.md
runbooks/redis-failure.md
