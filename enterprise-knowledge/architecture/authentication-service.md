# Authentication Service

| Field | Value |
| --- | --- |
| Document ID | ARCH-AUTH-001 |
| Document type | architecture |
| Service | authentication-service |
| Team | identity |
| Classification | internal |
| Last updated | 2026-05-20 |

## Purpose

authentication-service is the identity provider for the Aurora Commerce platform. It is owned by the identity team, runs on AKS in its own namespace, and issues OIDC/JWT access tokens to every other service. It stores session and refresh-token state exclusively in Azure Cache for Redis. It is one of the six services catalogued in `architecture/system-overview.md`.

authentication-service is on the critical path for every authenticated request. When its Redis store is unhealthy, the whole platform returns HTTP 401 responses even though the downstream services are healthy.

## Responsibilities

- Authenticate user and partner credentials.
- Issue OIDC/JWT access tokens.
- Issue and rotate refresh tokens.
- Validate token signatures and claims on behalf of callers.
- Maintain session state and device bindings.
- Read signing material and client secrets from Azure Key Vault `kv-aurora-prod`.

## Token model

| Token | Format | TTL | Storage |
| --- | --- | --- | --- |
| Access token | OIDC/JWT, RS256 | 15 minutes | Not stored server-side; validated by signature |
| Refresh token | Opaque random string | 30 days | Azure Cache for Redis |

Access tokens are short lived at 15 minutes so that revocation never has to reach them; a compromised access token expires quickly. Refresh tokens live for 30 days and are the real session credential, so they are stored in Redis and can be revoked immediately.

## Dependencies

| Dependency | Type | Notes |
| --- | --- | --- |
| Azure Cache for Redis, Standard C1 | Datastore | Shared with inventory-service cache |
| Azure Key Vault `kv-aurora-prod` | Secret store | Signing keys and client secrets |
| Application Insights | Telemetry | Login and token telemetry |

Redis is shared: authentication-service stores sessions and refresh tokens, while inventory-service uses the same instance as a cache. The cache instance is Standard C1 with a primary and a replica; a planned maintenance window triggers a primary failover, which is exactly what caused INC-2026-001.

## Interfaces

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/.well-known/openid-configuration` | GET | OIDC discovery |
| `/oauth2/token` | POST | Exchange credentials or refresh token for tokens |
| `/oauth2/introspect` | POST | Validate an opaque token |
| `/v1/sessions/{id}` | DELETE | Revoke a session |

## Data model in Redis

| Key pattern | Value | TTL |
| --- | --- | --- |
| `session:{sessionId}` | Session record with user and device binding | 30 days |
| `refresh:{tokenHash}` | Refresh-token record with rotation lineage | 30 days |
| `revoked:{jti}` | Access-token revocation marker | 15 minutes |

Session keys are the hot path. Every authenticated request performs a session lookup, so Redis latency is directly additive to authentication-service latency. The p95 latency SLO is under 250 ms.

## Failure modes

| Failure | Cause | Observable symptom |
| --- | --- | --- |
| Session lookup failures | Redis primary failover | Burst of HTTP 401 across all services |
| Session rebuild storm | Mass re-authentication after failover | Redis CPU and connection spike |
| Signing key unavailable | Key Vault access failure | Token issuance errors |

The failover handling procedure and the session rebuild storm watch are documented in `runbooks/redis-failure.md`. INC-2026-001 is the canonical example: a Redis primary failover during a planned maintenance window took 18 minutes to resolve and caused roughly 4% of login attempts to fail.

## Operational notes

- SLO: p95 latency under 250 ms.
- Secrets, including JWT signing keys and the NorthPay-facing client secret, are never written to logs. See `security/secrets-management.md`.
- Redis failover is detectable from Azure Monitor metrics before it becomes an authentication incident; see `runbooks/redis-failure.md`.
- Because the cache instance is shared, a heavy inventory cache warm-up can add pressure to the same server that holds sessions. Keep an eye on total Redis CPU during catalog deployments.

INC-2026-001 should be read together with `runbooks/redis-failure.md` before running a Redis maintenance window.

## Token issuance and validation flow

1. A client authenticates at `/oauth2/token` with credentials or a 30 day refresh token.
2. authentication-service verifies the credential and writes `session:{sessionId}` and `refresh:{tokenHash}` to Redis with a 30 day TTL.
3. It signs an RS256 JWT access token with a 15 minute TTL and returns it with the refresh token.
4. On each later request, the target service validates the token signature locally; it does not call authentication-service for every request.
5. Services that need an explicit revocation check call `/oauth2/introspect`, which reads `revoked:{jti}` from Redis.

Because validation is local, a compromised or revoked access token is only a risk for up to 15 minutes. After that it expires naturally; refresh tokens are the credential that can be revoked immediately.

## Capacity and scaling

- The service scales horizontally on AKS and holds no local session state, so any pod can serve any request.
- Redis is the only shared bottleneck. Session reads dominate, so keep `session:` lookups under 250 ms at p95 to stay within the service SLO.
- Because the Redis instance is shared with inventory-service, coordinate scaling changes and cache warm-ups with the catalog team.

## Security considerations

- JWT signing keys are read from `kv-aurora-prod` using a managed identity and are never logged. See `security/secrets-management.md`.
- Session identifiers and refresh tokens are opaque and are never written to telemetry; only token identifiers are logged.
- Refresh-token rotation invalidates the lineage when a token is replayed, which limits the blast radius of a stolen refresh token.

## Related documents

architecture/system-overview.md
runbooks/redis-failure.md
security/secrets-management.md
incidents/INC-2026-001.md
