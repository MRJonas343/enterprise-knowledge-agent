# Runbook: Database Latency

| Field | Value |
| --- | --- |
| Document ID | RB-DBLAT-001 |
| Document type | runbook |
| Service | payment-service |
| Team | payments |
| Classification | internal |
| Last updated | 2026-06-10 |

## Trigger

This runbook is triggered when **PgBouncer pool utilisation stays above 80% for 5 minutes**, which pages the on-call engineer through Azure Monitor. It also applies to any sustained rise in PostgreSQL query latency on the `payments` database, even before the alert fires.

The alert is deliberately set below saturation: by the time the pool reaches 100%, requests are queueing and checkout-api is already returning errors.

## Symptoms

- PgBouncer pool utilisation climbing toward and past 80% for longer than 5 minutes.
- payment-service p95 latency rising above its 600 ms SLO.
- checkout-api p95 latency rising above its 400 ms SLO and its error rate rising above 0.5%.
- PostgreSQL activity showing many long-running queries on the `payments` database.
- No deployment required for the symptom to appear, but a recent payment-service release is a strong suspect.

## Diagnosis steps

Run these steps in order. Each command targets the `payments` database unless stated otherwise.

1. Confirm the alert and the current pool state.

   ```bash
   kubectl -n payments get pods -l app=payment-service
   kubectl -n payments port-forward svc/pgbouncer 6432:6432
   psql "host=127.0.0.1 port=6432 dbname=payments" -c "SHOW POOLS;"
   ```

2. Identify the long-running queries holding connections.

   ```sql
   SELECT pid, usename, state, wait_event_type, wait_event,
          now() - query_start AS runtime, left(query, 120) AS query
   FROM pg_stat_activity
   WHERE state <> 'idle'
   ORDER BY runtime DESC
   LIMIT 20;
   ```

3. Correlate the slow statements with their call sites using the statement statistics view.

   ```sql
   SELECT queryid, calls, mean_exec_time, max_exec_time, rows,
          left(query, 120) AS query
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 20;
   ```

4. Check for lock contention that could be inflating runtime.

   ```sql
   SELECT pid, locktype, mode, granted, relation::regclass
   FROM pg_locks
   WHERE NOT granted;
   ```

5. Check for a sequential scan on a large table, which typically means a missing index.

   ```sql
   SELECT relname, seq_scan, seq_tup_read, idx_scan
   FROM pg_stat_user_tables
   ORDER BY seq_tup_read DESC
   LIMIT 20;
   ```

6. Confirm whether a recent deployment preceded the symptom.

   ```bash
   kubectl -n payments rollout history deployment/payment-service
   ```

## Decision points

- **A single statement dominates `pg_stat_statements` and a recent release shipped that statement.** Treat it as a release regression. Roll back payment-service to the previous known-good version following `engineering/rollback-procedure.md`. This is what resolved INC-2026-002.
- **A statement dominates but has been stable for weeks.** It is a data-growth problem, not a release problem. Open a database performance ticket and, if it is the finance reporting query, add the missing index.
- **No single statement dominates and utilisation is only mildly elevated.** Check pod count: more payment-service pods means more 50-connection pools. Scale down if a recent scale-up overshot.
- **Locks are the cause.** Identify the blocking PID and the offending transaction before terminating anything.
- **Pool pressure appears alongside CPU saturation from a retry storm.** Follow `runbooks/high-cpu.md` as well; INC-2026-003 combined both.

## Resolution

1. If a release regression is confirmed, roll back per `engineering/rollback-procedure.md`.
2. If a missing index is confirmed, add it concurrently so writes are not blocked:

   ```sql
   CREATE INDEX CONCURRENTLY idx_settlements_date_status
   ON settlements (settlement_date, status);
   ```

3. Confirm pool utilisation falls below 80% and stabilises.
4. Confirm payment-service p95 returns below 600 ms and checkout-api below 400 ms.
5. Record the incident identifier and link the query evidence in the incident record.

The release controls that should have prevented this class of regression are in `engineering/deployment-guidelines.md`.

## Escalation

- If pool utilisation does not fall after rollback, page the payments team lead.
- If the database server itself is degraded, page the platform team and open an Azure support request.
- If checkout-api error rate exceeds 5%, notify the checkout team; they may need to shed load manually because there is no circuit breaker on the payment-service client.

INC-2026-002 is the worked example for this runbook: pool exhaustion on the `payments` database raised checkout-api p95 to 840 ms and the error rate to 6%, resolved by rolling payment-service from v2.31.0 back to v2.30.4.

## Related documents

architecture/payment-service.md
incidents/INC-2026-002.md
runbooks/high-cpu.md
engineering/rollback-procedure.md
engineering/deployment-guidelines.md
