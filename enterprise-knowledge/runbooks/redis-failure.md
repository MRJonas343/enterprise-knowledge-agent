# Runbook: Redis Failure

| Field | Value |
| --- | --- |
| Document ID | RB-REDIS-001 |
| Document type | runbook |
| Service | authentication-service |
| Team | identity |
| Classification | internal |
| Last updated | 2026-05-20 |

## Trigger

This runbook is triggered by either of two events:

1. **Redis failover detection** — Azure Monitor reports that the Azure Cache for Redis Standard C1 primary has failed over to the replica.
2. **Session rebuild storm watch** — after a failover, authentication-service observes a sharp rise in re-authentication traffic and Redis operations per second.

The instance is shared: authentication-service stores sessions and refresh tokens, and inventory-service uses the same server as a cache. A failover therefore affects token validation and stock reads at the same time.

## Symptoms

- A burst of HTTP 401 responses across every service that validates tokens.
- authentication-service p95 latency rising above its 250 ms SLO.
- Redis session lookup failures in authentication-service logs.
- A session rebuild storm: a large spike in login attempts as clients re-authenticate.
- Redis CPU and connection count spiking immediately after failover.

## Failover handling

Azure Cache for Redis Standard C1 has a primary and a replica. During a failover the replica is promoted; the promotion itself is usually fast, but every connection through the old primary is dropped and must be re-established. The application behaviour during that window determines whether the failover becomes an incident.

1. Confirm the failover from Azure Monitor.

   ```bash
   az redis show \
     --name redis-aurora-prod \
     --resource-group rg-aurora-prod \
     --query "provisioningState"
   ```

2. Verify that authentication-service pods reconnect. The Redis client should retry with backoff, not fail permanently.

   ```bash
   kubectl -n identity logs -l app=authentication-service --tail=200 | grep -i redis
   ```

3. Inspect session lookup failure counts.

   ```kusto
   traces
   | where cloud_RoleName == "authentication-service"
   | where message contains "session lookup failed"
   | summarize count() by bin(timestamp, 1m)
   | order by timestamp desc
   ```

4. Check Redis server load and connected clients.

   ```bash
   redis-cli -h redis-aurora-prod.redis.cache.windows.net -p 6380 --tls info clients
   redis-cli -h redis-aurora-prod.redis.cache.windows.net -p 6380 --tls info stats
   ```

## Session rebuild storm

After a failover, all sessions that were only in the failed primary may be lost. Affected clients fall back to their 30-day refresh token and re-authenticate. This is the **session rebuild storm**: a legitimate, self-inflicted traffic spike that can keep Redis saturated after the failover itself has recovered.

Watch for:

- Login request count far above the normal baseline.
- `session:{sessionId}` writes climbing rapidly.
- Redis `instantaneous_ops_per_sec` staying elevated after failover recovery.

Mitigations:

1. Allow the storm to drain if Redis CPU is below 70% and error rates are stable.
2. If Redis CPU exceeds 70%, rate-limit login attempts by client and stagger re-authentication.
3. Confirm refresh tokens survived; if they did not, expect a second wave and notify the identity team lead.
4. Confirm inventory-service cache misses do not cascade into `catalog` database overload; if they do, coordinate with the catalog team.

## Decision points

- **Failover recovered and no storm.** Close the alert after confirming latency is back within SLO.
- **Failover recovered but storm is ongoing.** Apply login rate limiting and keep monitoring.
- **Failover did not recover within 10 minutes.** Escalate to Azure support and the identity team lead; consider failing back manually.
- **Refresh tokens were lost.** Treat as a full logout event and communicate to partners.

## Resolution

1. Confirm the promoted replica is serving reads and writes.
2. Confirm authentication-service session lookups succeed again.
3. Confirm the 401 burst has stopped across all services.
4. Confirm latency for authentication-service, payment-service and checkout-api is within SLO.
5. Record the incident with the failover timeline and the number of failed login attempts.

## Escalation

- Page the identity team lead if failover does not recover within 10 minutes.
- Page the platform team if the shared Redis instance shows a second failover.
- Open an Azure support request if the Standard C1 instance reports an unhealthy node.
- The Redis access key used by authentication-service is stored and rotated in Key Vault; see `security/secrets-management.md`.

INC-2026-001 is the recorded instance of this pattern: a planned Redis maintenance window caused a primary failover, authentication-service session lookups failed, and roughly 4% of login attempts failed over 18 minutes on 2026-02-11.

## Related documents

architecture/authentication-service.md
incidents/INC-2026-001.md
security/secrets-management.md
