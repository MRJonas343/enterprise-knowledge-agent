# Phase 12 Observability Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-20 |
| Phase | Phase 12, Observability |
| Environment | Local process against the deployed `canadacentral` resources |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 12 exit criteria, as trimmed for this project:

> A request can be diagnosed across the gateway and the agent without exporting
> prompts, answers, retrieved documents, tokens or personal data.

The original roadmap row also asked for alerting, dashboards and capacity
metrics. Those assume an operated service, which this is not, and they are
recorded below as deliberately out of scope rather than deferred.

## Scope

Two halves, and only one of them was missing.

- **The agent was already traced.** A Log Analytics workspace and an Application
  Insights resource exist, connected to the Foundry project, and agent runs are
  readable as spans in the Foundry portal. That was authorised earlier as a
  narrow observability exception and it is unchanged.
- **The gateway had nothing.** Every request it served was invisible. This phase
  instruments it.

## What was built

`src/enterprise_knowledge_agent/api.py` gains `_configure_telemetry`, called once
at import. It exports the gateway's own HTTP request spans and metrics to the
same Application Insights the agent reports to.

No dependency was added. Every piece was already present as a transitive
dependency: `configure_otel_providers` from `agent_framework.observability`,
`FastAPIInstrumentor` from `opentelemetry-instrumentation-fastapi`, and
`AzureMonitorTraceExporter` / `AzureMonitorMetricExporter`.

Three properties are deliberate:

- **Sensitive data stays off.** `enable_sensitive_data=False` is passed
  explicitly. Prompts, answers and retrieved documents are never exported. The
  framework defaults to off; the explicit argument makes the choice visible so
  it cannot be flipped by accident.
- **Telemetry can never break the gateway.** The whole configuration is wrapped
  in `try/except Exception`, which logs and continues. A missing connection
  string is a normal state, not an error. A gateway that cannot export still
  serves.
- **The connection string is never logged**, in whole or in part.

`tests/conftest.py` is new. `api.py` loads the developer's `.env` at import, and
that `.env` carries a live connection string, so without a guard the suite would
configure real exporters and export telemetry while the tests ran. The conftest
sets `OTEL_SDK_DISABLED`, which the configuration checks first.

## Evidence

### 1. The two defects that live verification found

The wiring was written first and looked correct. Driving a real request through
the instrumented app and exporting to the live resource found two faults that
would otherwise have shipped as working code that exported nothing.

**First: 401 Unauthorized.** A connection string alone cannot authenticate.
Both tracing resources set `local_authentication_enabled = false`, so the
connection string identifies the target and carries no key. Entra ID is the only
way in — the same keyless rule the rest of this repository follows. The
exporters now take a `DefaultAzureCredential`.

**Second: 403 Forbidden.** With a credential attached, the response changed to
403 and named the cause: the resource "has the correct `Monitoring Metrics
Publisher` role assigned" was missing. The operator's identity held
`Log Analytics Reader` and `Privileged Monitoring Data Reader` — it could read
traces and not publish them. Only the project identity held the publisher role.

`infra/terraform/tracing.tf` now grants `Monitoring Metrics Publisher` to the
operator. It is publish-only: the two reader roles are unchanged.

### 2. The export reaches Application Insights

```text
tracer provider: TracerProvider            (a real SDK provider, not the no-op proxy)
GET /api/health -> 200 {'status': 'ok', 'agent': 'aurora-knowledge-agent'}
force_flush returned: True (1.6s)
exporter warnings or errors seen: 0
>>> telemetry reached Azure
```

The request was driven through the real, instrumented FastAPI app. The span was
exported to the live resource with no error.

After the grant, a short wait was still required before ingestion accepted the
token. Role assignments propagate on Azure's schedule, not Terraform's: the
grant was already visible in the resource's role assignment list while ingestion
still returned 403.

### 3. The guard is real, not cosmetic

```text
OTEL_SDK_DISABLED unset -> TracerProvider
OTEL_SDK_DISABLED=true  -> ProxyTracerProvider
```

`ProxyTracerProvider` is OpenTelemetry's no-op default, so with the guard set
nothing is configured at all. The distinction is observed from the global tracer
provider rather than inferred from a log line.

### 4. The suite is unaffected

```text
90 passed, 1 warning
```

## Known limitations and open items

- **A caller cannot be identified from the trace.** The spans carry the route,
  the status and the duration, not who asked. The audit gap recorded in the
  Phase 9 acceptance is therefore still open; this phase narrows what can be
  diagnosed, not who is accountable.
- **Whether the gateway span parents the agent's span is not verified.** Both
  land in the same Application Insights, so they are visible side by side. True
  single-trace correlation would need the trace context to propagate into
  Foundry, which was not established.
- **No alerting, no dashboards and no capacity metrics.** Out of scope by
  decision. Nothing is operated, so there is nothing to alert.
- **Metrics are whatever the exporter emits by default.** No custom metric was
  added and no price model is applied.
- **Traces are still readable only by a privileged role.** GenAI payloads
  require `Privileged Monitoring Data Reader`, as recorded in the Phase 9
  exception.
- **The gateway's telemetry is only exercised when a request is served.** A
  process that never receives one exports nothing, which is correct but also
  means a quiet deployment looks identical to a broken one.

## What this gate does not cover

- **No distributed tracing across the Foundry boundary.** See above.
- **No log correlation or redaction policy beyond sensitive data being off.**
- **No SLO, no burn rate, no alert routing.**
- **No evaluation signals.** Those belong to Phase 11 and run separately.

## Acceptance

The Phase 12 exit criteria, as trimmed, are met. A request served by the gateway
produces a span that reaches Application Insights, and prompts, answers,
retrieved documents and credentials are not exported.

The phase is accepted on evidence produced against the live resource rather than
on the wiring looking right. That distinction is the whole value of this record:
the first version of this code was plausible, passed every test, and exported
nothing at all.
