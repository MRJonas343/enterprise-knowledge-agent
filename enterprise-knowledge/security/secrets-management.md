# Secrets Management

| Field | Value |
| --- | --- |
| Document ID | SEC-SECRETS-001 |
| Document type | security |
| Service | platform-wide |
| Team | security |
| Classification | internal |
| Last updated | 2026-05-25 |

## Purpose

This document defines how Aurora Commerce stores, accesses, rotates and protects secrets. A secret is any value whose disclosure would grant access to a system: credentials, API keys, connection strings, tokens, certificates and signing keys. The central rule is that secrets live in Azure Key Vault and are accessed by workloads through managed identity. They never appear in code, images or logs.

## Scope

It applies to every service and every environment. The single production Key Vault instance is `kv-aurora-prod`. The services that hold the most sensitive material are authentication-service (JWT signing keys and session store credentials) and payment-service (NorthPay credentials).

## Secret inventory

| Secret | Consumer | Rotation interval | Storage |
| --- | --- | --- | --- |
| NorthPay API credential | payment-service | 90 days | `kv-aurora-prod` |
| JWT signing key (RS256) | authentication-service | 180 days | `kv-aurora-prod` |
| Redis access key | authentication-service, inventory-service | 90 days | `kv-aurora-prod` |
| PostgreSQL credentials | payment-service, order-service, inventory-service | 90 days | `kv-aurora-prod` |
| Service Bus connection credential | notification-service, payment-service | 90 days | `kv-aurora-prod` |

## Access model

- **Managed identity only.** Each AKS workload has a managed identity. That identity is granted `get` on the specific secrets it needs, scoped to `kv-aurora-prod`. No workload uses a shared credential to read Key Vault.
- **No static credentials in the cluster.** There is no Key Vault credential file, no service principal password and no connection string mounted into a pod.
- **Least privilege.** A workload can read only its own secrets. payment-service cannot read the JWT signing key, and notification-service cannot read NorthPay credentials.
- **Audited access.** Every Key Vault read is logged and retained for security review.

The standard runtime pattern is the Key Vault provider for the Secrets Store CSI driver or the Azure Identity SDK; either way the secret is fetched at runtime using the pod managed identity.

## Prohibition on secrets in code

This is absolute, and it is enforced by policy and by the build pipeline:

1. No secret is committed to the repository, including test fixtures and examples.
2. No secret is baked into a container image.
3. No secret is set as a literal value in a Kubernetes manifest.
4. No secret is printed, logged or included in an error message.
5. No secret is copied into a ticket, a chat message or a document.

## Prohibition on logging secrets

Secrets and anything that could reconstruct a secret must never reach a log sink:

- Do not log the value of an authorization header, an API key or a connection string.
- Do not log full token bodies. Log a token identifier or a key ID instead.
- Do not log database connection strings with embedded credentials.
- Redact or hash sensitive fields before they enter telemetry; Application Insights is not a secret store.

authentication-service in particular must never log JWT signing material or refresh-token values. It logs token identifiers and session identifiers only. See `architecture/authentication-service.md`.

## Rotation

1. Create the new secret version in `kv-aurora-prod`.
2. Deploy the consumer change through the standard pipeline described in `engineering/deployment-guidelines.md`, with the security team approving as the secret-owner approver.
3. Verify the consumer reads the new version and operates normally.
4. Disable, then delete, the old version after the rotation interval has elapsed.
5. Record the rotation date and the secret version in the security register.

Rotation must be a routine, canary-tested change. A secret rotation is a deployment like any other and follows the change approval rules; it is never applied by editing a live cluster by hand.

## Enforcement

- Static analysis in the build pipeline includes secret scanning and fails the build on a match.
- Access to `kv-aurora-prod` is granted only through managed identity, reviewed quarterly.
- Every rotation is logged and reviewed; overdue rotations are reported to the security team.
- Access to Key Vault is audited, and unexpected reads are investigated.
- A leaked secret is treated as an incident: rotate immediately, then investigate exposure.
- Secret rotation status is reviewed monthly, and any overdue rotation is escalated to the owning team.
- No workload is granted `list` on `kv-aurora-prod`; only named `get` permissions are granted.
- Break-glass Key Vault access is time-boxed, requires security approval and is logged.

## Secret delivery to workloads

1. The pod authenticates to `kv-aurora-prod` using its managed identity.
2. It requests only the named secret it is authorized for.
3. The secret is held in memory for the process lifetime and is never written to disk.
4. On rotation, the pod receives the new version after a restart through the standard pipeline.

No secret is passed as a plain environment variable value in a manifest; the manifest references the Key Vault secret name, and the managed identity resolves the value at runtime.

## Response to a leaked secret

1. Rotate the secret immediately in `kv-aurora-prod` and disable the old version.
2. Roll the consumer through the pipeline so it picks up the new version.
3. Review Key Vault audit logs and telemetry for unauthorized use.
4. Redact the secret from any log, ticket or document where it appeared.
5. Record the incident and complete a root-cause review.

## Related documents

engineering/deployment-guidelines.md
architecture/authentication-service.md
