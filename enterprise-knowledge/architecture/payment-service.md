# Payment Service

| Field | Value |
| --- | --- |
| Document ID | ARCH-PAY-001 |
| Document type | architecture |
| Service | payment-service |
| Team | payments |
| Classification | internal |
| Last updated | 2026-06-10 |

## Purpose

payment-service authorizes, captures and settles payments for the Aurora Commerce platform. It is owned by the payments team, runs on AKS in its own namespace, and stores all durable state in the PostgreSQL `payments` database. It is the only service that talks to NorthPay, the external payment service provider (PSP).

payment-service is the single most incident-prone service in the platform. Two of the three recorded incidents, INC-2026-002 and INC-2026-003, originated here, both rooted in the same unindexed reporting query on the `payments` database. It is one of the six services listed in `architecture/system-overview.md`.

## Responsibilities

- Authorize a payment against a NorthPay payment method.
- Capture or void a previously authorized payment.
- Record settlement status and reconcile it with NorthPay.
- Publish payment lifecycle events to the `payment-events` Service Bus topic.
- Serve internal reporting queries used by the finance team.

## Dependencies

| Dependency | Type | Notes |
| --- | --- | --- |
| PostgreSQL `payments` database | Datastore | Accessed only through PgBouncer |
| PgBouncer | Connection pooler | Pool size 50 per pod |
| NorthPay | External PSP | HTTPS API, guarded by a circuit breaker |
| Azure Key Vault `kv-aurora-prod` | Secret store | NorthPay credentials via managed identity |
| `payment-events` topic | Service Bus | Outbound asynchronous events |
| Application Insights | Telemetry | Traces, dependency calls and metrics |

payment-service is a leaf service from the platform's perspective: it calls NorthPay but no other Aurora service. checkout-api calls payment-service, not the other way around.

## Interfaces

The public interface is HTTPS and versioned under `/v1`:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/v1/payments/authorize` | POST | Authorize a payment |
| `/v1/payments/{id}/capture` | POST | Capture an authorization |
| `/v1/payments/{id}/void` | POST | Void an authorization |
| `/v1/payments/{id}` | GET | Read payment status |

checkout-api calls `/v1/payments/authorize` synchronously with a 2 second timeout. The payment-service p95 latency SLO is under 600 ms, which leaves only a small margin before the checkout-side timeout fires. See `architecture/checkout-service.md`.

## Data model

The `payments` database contains:

- `payment_attempts` — one row per authorization attempt, with the NorthPay reference and outcome.
- `payment_captures` — capture records linked to an attempt.
- `settlements` — daily settlement lines imported from NorthPay.
- `payment_events_outbox` — transactional outbox for the `payment-events` topic.

The reporting query used by the finance team filters on `settlements.settlement_date` and `settlements.status`. During INC-2026-002 it was discovered that no index existed on the combined filter columns, so the query performed a sequential scan on a large table.

## Connection pooling

All database access goes through PgBouncer in transaction pooling mode. Each payment-service pod opens a pool of 50 connections. With the normal pod count this stays comfortably under the PostgreSQL server connection limit, but it means a single misbehaving query is heavily duplicated across pods.

Pool utilisation above 80% sustained for 5 minutes pages the on-call engineer. The diagnostic procedure is in `runbooks/database-latency.md`.

## Failure modes

| Failure | Cause | Observable symptom |
| --- | --- | --- |
| Connection pool exhaustion | Long-running query holds connections | Rising p95, checkout-api 5xx, pool utilisation near 100% |
| NorthPay retry storm | Unbounded retries on NorthPay errors | Pod CPU saturation above 85%, p95 breach |
| Slow reporting query | Missing index on settlement filter columns | Sustained pool utilisation, elevated query time |

The safe response to a release-induced failure is a version rollback rather than a hotfix. See `engineering/rollback-procedure.md`. CPU saturation from a NorthPay retry storm is handled by `runbooks/high-cpu.md`, and the release and canary controls that gate a new query are in `engineering/deployment-guidelines.md`.

## Operational notes

- SLO: p95 latency under 600 ms as measured at the service ingress.
- Current baseline release during the April 2026 incident window: v2.30.4 (stable) and v2.31.0 (bad).
- NorthPay client settings changed after INC-2026-003: bounded retry budget and a circuit breaker.
- The missing index on the settlement filter columns was added after INC-2026-003.
- Secrets are never read from configuration files; the NorthPay credential is fetched from `kv-aurora-prod` using the pod managed identity. See `security/secrets-management.md`.

INC-2026-002 is the canonical worked example of a payment-service pool exhaustion incident and is worth reading alongside `runbooks/database-latency.md`.

## Release history and client settings

| Release | Window | Outcome |
| --- | --- | --- |
| v2.30.4 | before 2026-04-12 | Known-good rollback target for INC-2026-002 |
| v2.31.0 | deployed 2026-04-12 | Introduced the unindexed reporting query; rolled back the same day |

After INC-2026-003 the NorthPay client gained two controls: a bounded retry budget and a circuit breaker. When the breaker is open, authorize calls fail fast instead of amplifying call volume, and a `northpay.circuit.open` event is emitted for alerting. Together these stop a slow NorthPay from turning into a CPU incident.

## Monitoring

- PgBouncer pool utilisation is exported as a metric; above 80% for 5 minutes pages the on-call engineer.
- Pod CPU above 85% for 10 minutes pages the on-call engineer.
- NorthPay dependency duration and error rate are tracked in Application Insights.
- checkout-api p95 is watched as a proxy for payment-service health, because checkout-api inherits payment latency through its synchronous call.

## Related documents

architecture/checkout-service.md
architecture/system-overview.md
runbooks/database-latency.md
runbooks/high-cpu.md
incidents/INC-2026-002.md
incidents/INC-2026-003.md
engineering/rollback-procedure.md
engineering/deployment-guidelines.md
security/secrets-management.md
