# Runbook: High CPU

| Field | Value |
| --- | --- |
| Document ID | RB-CPU-001 |
| Document type | runbook |
| Service | payment-service |
| Team | payments |
| Classification | internal |
| Last updated | 2026-06-10 |

## Trigger

This runbook is triggered when **pod CPU stays above 85% for 10 minutes**, which pages the on-call engineer through Azure Monitor. It applies to any Aurora Commerce service, but it is written with payment-service in mind because that service produced the only recorded CPU saturation incident, INC-2026-003.

The 10 minute window is intentional: a normal deployment briefly spikes CPU while the new pods warm up, and the runbook should not fire for that.

## Symptoms

- One or more pods reporting CPU utilisation sustained above 85%.
- Rising p95 latency for the affected service (payment-service SLO is under 600 ms).
- checkout-api p95 latency rising above its 400 ms SLO as it waits on the synchronous payment-service call.
- Application Insights dependency telemetry showing repeated calls to NorthPay with long durations.
- In the INC-2026-003 pattern, high CPU in payment-service alongside elevated database pool utilisation.

## Diagnosis steps

Run these steps in order.

1. Identify which pods are hot and how many.

   ```bash
   kubectl -n payments top pods -l app=payment-service
   ```

2. Check recent restarts and rollout state.

   ```bash
   kubectl -n payments get pods -l app=payment-service
   kubectl -n payments rollout history deployment/payment-service
   ```

3. Inspect Application Insights dependency telemetry for the NorthPay client.

   ```kusto
   dependencies
   | where cloud_RoleName == "payment-service"
   | where target contains "northpay"
   | summarize count(), avg(duration), max(duration) by bin(timestamp, 1m)
   | order by timestamp desc
   ```

4. Determine whether a retry storm is inflating call volume. Compare the NorthPay call rate against the inbound authorization rate; a ratio well above 1 indicates retry amplification.

   ```kusto
   requests
   | where cloud_RoleName == "payment-service"
   | summarize inbound = count() by bin(timestamp, 1m)
   ```

5. Check whether the CPU is caused by a database query rather than network retries.

   ```bash
   kubectl -n payments exec deploy/payment-service -- \
     curl -s localhost:8080/actuator/metrics/jvm.cpu.usage
   ```

   If CPU is query-bound rather than retry-bound, follow `runbooks/database-latency.md` instead.

6. Confirm that the circuit breaker on the NorthPay client is enabled and observed.

   ```kusto
   customEvents
   | where name == "northpay.circuit.open"
   | summarize count() by bin(timestamp, 5m)
   | order by timestamp desc
   ```

## Decision points

- **NorthPay call rate far exceeds inbound rate and CPU is retry-bound.** A retry loop is the cause. Confirm the circuit breaker is open, reduce the retry budget, and page the payments team to adjust client settings.
- **CPU is query-bound with pool utilisation also high.** Treat it as a database problem; follow `runbooks/database-latency.md`.
- **The symptom began within minutes of a deployment.** Suspect the release. Roll back following `engineering/rollback-procedure.md`.
- **CPU is high but latency and error rate are within SLO.** Do not act yet; continue observation and confirm the alert is not a transient warm-up.

## Resolution

1. Reduce or disable the runaway retry path so CPU stops climbing.
2. If the circuit breaker is not tripping, temporarily lower the retry budget via configuration and restart the deployment.
3. Add horizontal capacity only as a stabiliser, not as the fix; more pods can worsen pool pressure.
4. Roll back the offending release if one is implicated.
5. Confirm CPU returns below the 85% threshold and stays there for 15 minutes.
6. Confirm payment-service and checkout-api latency return within SLO.

## Escalation

- If CPU does not fall after disabling retries, page the payments team lead.
- If NorthPay is confirmed degraded, engage the vendor through the standard support channel and keep the circuit breaker open.
- If checkout-api error rate exceeds 5%, notify the checkout team.
- Deployment and canary controls that gate a payment-service client change are defined in `engineering/deployment-guidelines.md`.

INC-2026-003 is the recorded instance of this pattern: payment-service pod CPU saturated at 95% for 22 minutes because of a runaway retry loop against NorthPay combined with the same unindexed reporting query seen in INC-2026-002. The permanent fixes were a retry budget, a circuit breaker on the NorthPay client, and adding the missing index.

## Related documents

architecture/payment-service.md
incidents/INC-2026-003.md
runbooks/database-latency.md
engineering/deployment-guidelines.md
