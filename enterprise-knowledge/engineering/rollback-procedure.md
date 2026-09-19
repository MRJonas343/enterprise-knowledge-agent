# Rollback Procedure

| Field | Value |
| --- | --- |
| Document ID | ENG-ROLLBACK-001 |
| Document type | engineering |
| Service | platform-wide |
| Team | platform |
| Classification | internal |
| Last updated | 2026-06-15 |

## Purpose

This document defines how to roll back a deployment on Aurora Commerce. It provides a generic procedure followed by service-specific steps for checkout-api and payment-service. Rollback is the preferred first response to a release-induced incident, because restoring a known-good version is faster and safer than shipping a hotfix under pressure.

INC-2026-002 is the reference case: rolling payment-service from v2.31.0 back to v2.30.4 restored checkout-api from 840 ms p95 and a 6% error rate to within SLO.

## Scope

It applies to every service deployed through the pipeline described in `engineering/deployment-guidelines.md`. Read that document alongside this one so the rollback target and the canary state are understood.

## When to roll back

Roll back when a change is the likely cause and the impact is user-visible:

- A service SLO is breached after a deployment (p95 or error rate).
- A canary health check fails at any rollout step.
- A database pool or CPU alert fires shortly after a release.
- A dependency behaves differently after a client change.

Do not roll back for a transient warm-up spike; give the canary its 10 minute window first.

## Generic rollback steps

1. Declare the rollback and open or attach it to an incident identifier.
2. Identify the rollback target: the previous known-good image tag. For payment-service during INC-2026-002 that was v2.30.4.
3. Halt any in-progress progressive rollout so no further traffic shifts to the bad version.
4. Apply the previous image tag to the Deployment.
5. Watch the rollout until all pods run the target version.
6. Verify service SLOs return within bounds for 15 minutes.
7. Confirm dependent services recovered, then close the incident.
8. Record the rollback in the incident record with the version pair.

```bash
# Example: halt rollout and roll back a Deployment
kubectl -n payments rollout undo deployment/payment-service
kubectl -n payments rollout status deployment/payment-service
kubectl -n payments get pods -l app=payment-service -o jsonpath="{.items[*].spec.containers[*].image}"
```

If the rollback target is not simply the previous revision, set the image explicitly:

```bash
kubectl -n payments set image deployment/payment-service \
  payment-service=registry.aurora.example/payment-service:v2.30.4
```

## Service-specific steps: payment-service

payment-service has database state, so verify the schema is compatible with the target version before rolling back.

1. Confirm the target version does not require a schema migration that the bad release introduced.
2. Halt the rollout and set the image to the rollback target.
3. Watch PgBouncer pool utilisation; it should fall below 80% within a few minutes.
4. Confirm the NorthPay client retry budget and circuit breaker settings match the target version.
5. Confirm payment-service p95 returns below 600 ms.
6. Confirm checkout-api p95 returns below 400 ms and its error rate below 0.5%.
7. If the bad release added an index, leave the index in place; an added index is backward compatible and removing it risks new scans.

## Service-specific steps: checkout-api

checkout-api is stateless, so a rollback is simpler and safer.

1. Halt the rollout and set the image to the previous tag.
2. Restart the Deployment; in-flight checkouts fail cleanly and no state is corrupted.
3. Confirm checkout-api p95 returns below 400 ms and its error rate below 0.5%.
4. Confirm the downstream services (payment-service, inventory-service, order-service) show normal traffic.
5. Confirm no orphaned stock reservations remain from failed checkouts.

```bash
# checkout-api rollback
kubectl -n checkout rollout undo deployment/checkout-api
kubectl -n checkout rollout status deployment/checkout-api
```

Current checkout-api version is v3.7.2 and it is not implicated in any incident, so it has never needed a documented rollback in production.

## Verification after rollback

| Check | Expected |
| --- | --- |
| Target pods running | All pods on the rollback target image |
| Service p95 | Within the service SLO |
| checkout-api error rate | Under 0.5% |
| PgBouncer pool utilisation | Below 80% for payment-service |
| Dependent service latency | Within SLO |
| Alerts | Cleared and staying clear for 15 minutes |

## Related documents

engineering/deployment-guidelines.md
incidents/INC-2026-002.md
