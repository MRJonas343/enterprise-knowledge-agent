# Deployment Guidelines

| Field | Value |
| --- | --- |
| Document ID | ENG-DEPLOY-001 |
| Document type | engineering |
| Service | platform-wide |
| Team | platform |
| Classification | internal |
| Last updated | 2026-06-15 |

## Purpose

This document defines the standard deployment process for every Aurora Commerce service on AKS. It exists so that a release is repeatable, reviewable and reversible regardless of which team ships it. It is written after INC-2026-002, which showed that a release containing an unindexed reporting query could degrade checkout-api to 840 ms p95 and a 6% error rate within minutes.

## Scope

It applies to all six services: checkout-api, payment-service, order-service, inventory-service, authentication-service and notification-service. It covers the pipeline stages, the canary rollout strategy, change approval and the rule that secrets never live in code. Service-specific rollback steps live in `engineering/rollback-procedure.md`.

## Pipeline stages

Every change moves through the same stages. A stage that fails blocks the release; there is no manual override.

| Stage | Purpose | Blocking condition |
| --- | --- | --- |
| 1. Build | Compile and package the container image | Build failure |
| 2. Unit tests | Verify behaviour in isolation | Any failing test |
| 3. Static analysis | Lint, dependency and secret scanning | Any high-severity finding |
| 4. Integration tests | Verify against ephemeral dependencies | Any failing test |
| 5. Approval | Human change approval | Missing approval |
| 6. Canary deploy | Roll out to a small pod subset | Canary health check failure |
| 7. Progressive rollout | Shift traffic to the full fleet | SLO breach during rollout |
| 8. Post-deploy watch | Confirm SLOs for 30 minutes | SLO breach |

## Canary rollout

Every production deployment uses a canary:

1. Deploy the new version to one pod and keep the previous version running.
2. Route 5% of traffic to the canary for 10 minutes.
3. Watch error rate and p95 latency against the service SLO. For payment-service that is p95 under 600 ms; for checkout-api p95 under 400 ms and error rate under 0.5%.
4. If the canary is healthy, increase to 25%, then 50%, then 100% in 10 minute steps.
5. If the canary breaches an SLO at any step, halt and roll back following `engineering/rollback-procedure.md`.

Database-affecting releases must additionally watch PgBouncer pool utilisation during the canary. The pool check exists because the INC-2026-002 regression only became visible under production query volume, not in the pre-deployment test suite.

## Change approval

| Change class | Required approval |
| --- | --- |
| Application code, no schema change | One peer reviewer |
| New or changed database query | Peer reviewer plus a database index review |
| Schema migration | Payments or orders database owner plus platform |
| Secret or credential rotation | Security team |
| Infrastructure change | Platform team |

Approval is required before stage 5. The approver must confirm that any new reporting or analytics query has an index covering its filter columns; this is the specific control added after INC-2026-002.

## Secrets

Secrets never live in code. This is absolute and applies to every stage and every environment:

- No credential, API key, connection string, token or certificate is committed to the repository.
- No secret is baked into a container image or passed as a plain environment variable value in a manifest.
- AKS workloads read secrets from Azure Key Vault `kv-aurora-prod` using a managed identity.
- The static analysis stage includes secret scanning and fails the build on a match.

The full policy, rotation intervals and the prohibition on logging secrets are in `security/secrets-management.md`.

## Enforcement

- The pipeline is the only path to production. Manual `kubectl apply` of an application Deployment is not permitted outside a break-glass incident, and any break-glass change must be reconciled into the repository within one business day.
- Canary health checks are automated; a failed check blocks progression.
- Post-deploy watch is mandatory. A release is not considered complete until the 30 minute watch passes.
- Every rollback performed under this policy is recorded with the incident identifier, as was done for INC-2026-002.

## Operational notes

- Deploy during business hours unless the change is itself an incident response.
- One service per deployment. Do not bundle releases from multiple services.
- Keep the previous image tag available for at least 30 days so a rollback target always exists.
- payment-service release naming is semantic: v2.31.0 was the defective release and v2.30.4 was the rollback target in INC-2026-002.

## Environments

| Environment | Purpose | Deploy trigger |
| --- | --- | --- |
| Development | Fast iteration | On merge to the service branch |
| Staging | Integration and load testing | On release candidate |
| Production | Customer traffic | On approved release |

Production is the only environment with a canary stage. Staging must include a load test that exercises any new query at production scale; the INC-2026-002 regression passed staging precisely because that production-scale load was missing.

## Rollback linkage

Every deployment records its rollback target at approval time. If a release breaches an SLO during canary or during the post-deploy watch, halt progression immediately and follow `engineering/rollback-procedure.md`. The rollback target for the release involved in INC-2026-002 was recorded as payment-service v2.30.4 before v2.31.0 was approved, which is why the rollback decision took under two minutes.

## Related documents

engineering/rollback-procedure.md
security/secrets-management.md
incidents/INC-2026-002.md
