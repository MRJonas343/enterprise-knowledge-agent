# Phase 9 Security Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-20 |
| Phase | Phase 9, Security |
| Environment | Local process against the deployed `canadacentral` resources |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 9 exit criteria are:

> Security controls are evidenced, credentials remain externalized, protected
> content is denied safely, and governance risks have owners and mitigations.

All four are covered. The phase was deliberately narrowed before it started, and
the narrowing is part of the record rather than an omission.

## Scope

Phase 9 hardens the surface that already exists. Three items from the original
roadmap row were trimmed and two phases were retired:

| Item | Disposition |
| --- | --- |
| Network and data controls | **Out of scope.** Infrastructure hardening with no place in a portfolio-scale RAG demonstration, and private endpoints would break the operator's local development path. The storage account, the search service and the Foundry project keep their default public network access, and nothing in this phase claims otherwise. |
| Data retention | **Out of scope.** No soft-delete, retention policy or document lifecycle. Blob versioning stays enabled, but that is a recovery property, not a retention policy. |
| Audit logging | **Deferred.** There is no persisted record of who asked what. |
| Phases 7 and 8 | **Retired.** The agent's only tool is the knowledge base, executed server side by Foundry Agent Service, so neither a runtime-tool framework nor an MCP layer would have a consumer. |

## Identity boundaries

The gateway authenticates every caller before doing anything else.

`src/enterprise_knowledge_agent/api.py` resolves a bearer token through
`require_caller`, which parses `API_TOKENS` as `name:token` pairs and compares with
`secrets.compare_digest`. The comparison is time-independent, and both an absent
header and an unknown token return the same 401 body, so a caller learns only that
they are not authenticated.

The endpoint **fails closed**. With `API_TOKENS` unset or empty the dependency
raises 503 rather than treating "no tokens configured" as "no authentication
required". A half-typed entry is skipped and the valid entries kept, so one bad
pair cannot take the gateway down or silently open access.

A conversation is owned by the caller that opened it. A different caller
presenting a leaked conversation id gets **404, not 403**: confirming that someone
else's conversation exists is itself a disclosure.

Each caller has a fixed-window request quota, evaluated after authentication, so
an unauthenticated request never reaches the agent or the limiter.

## Protected content

A Responsible AI guardrail (`strict-guardrail`) is attached to the chat model
deployment. It declares 16 filters in `Blocking` mode: the four harm categories at
a medium threshold on both prompt and completion, and the binary filters for
jailbreak, indirect attack, profanity and protected material.

Two properties of this configuration are load-bearing and were established by
measurement rather than assumption:

1. **A severity threshold on a binary filter silently disables it.** With
   `severityThreshold` present, a jailbreak returned
   `{"jailbreak": {"detected": true, "filtered": false}}` — annotated, never
   blocked. Azure's own policies (`Microsoft.Default`, `Microsoft.DefaultV2`,
   `Microsoft.MAIDefault`) declare every binary filter without a threshold.
2. **The agent inherits the deployment's guardrail.** It declares no `rai_config`
   of its own, and none is needed.

A blocked turn reaches the client as **400** with
`"Blocked by a content safety policy. Rephrase the question and try again."`, not
as the 502 used for genuine failures. `_is_content_filter_error` walks the
exception chain and recognises the typed exception the Foundry client actually
raises. It is status-aware, so a 500 or a 429 that merely carries a filter code
stays a 502, and it cannot raise while classifying, because raising there would
turn the 400 it exists to produce into a 500.

Citation links are scoped rather than broadly signed. `corpus_blob_target` refuses
any URL outside the configured storage account and knowledge container before a
short-lived, read-only SAS is minted, and rejects traversal, non-https schemes and
lookalike hosts.

## Credentials

- Storage disables shared key access; Azure AI Search and both tracing resources
  disable local authentication. Every component uses a managed identity with a
  scoped role, including the `Storage Blob Delegator` grant the gateway needs to
  mint user-delegation SAS links.
- `.env` and Terraform state are git-ignored. The working tree was scanned for
  subscription identifiers, account keys, instrumentation keys, SAS signatures,
  passwords and private keys before the change was committed; the scan was clean.
- No credential appears in this record.

## Governance risks

Every known risk, with its control and its disposition. The project owner carries
every disposition recorded here.

| Risk | Control | Disposition |
| --- | --- | --- |
| Direct prompt injection / jailbreak | The binary jailbreak filter, verified blocking | **Controlled** |
| Indirect prompt injection through retrieved documents | None. The guardrail sees the caller's message and the completion, not the documents the agent retrieves | **Accepted.** Bounded by the agent having exactly one tool and that tool being read-only retrieval, so a successful injection can produce a wrong answer but cannot take an action. Phase 10. |
| Citation used to reach content outside the corpus | `corpus_blob_target` refuses anything outside the account and container | **Controlled** |
| Caller token shared or leaked | Per-caller identity, conversation ownership, per-caller quota | **Mitigated.** Tokens are static and have no rotation story. |
| Frontend token readable by anyone loading the page | None within this phase | **Accepted.** Documented as a limitation. The correct fix is a server-side proxy route, not a build-time value. |
| Service failure misreported as a caller error | Status-aware classification | **Controlled.** A 5xx or 429 carrying a filter code stays a 502. |
| Denial of service through cost or memory | Per-caller rate limit | **Partially mitigated.** The limiter is per-process and in-memory, and the session store has no eviction. |
| No access audit trail | Agent tracing records the agent's own runs as spans | **Deferred.** Traces carry no caller identity and are not an access log. |
| Public network exposure of the Azure resources | None | **Accepted by explicit scope decision.** Recorded in the roadmap. |

## Evidence

### 1. Contract suite

```text
48 passed, 1 warning in 1.79s
```

Azure is never called. `get_agent` is overridden with a fake returning real
agent-framework response objects. The security-relevant cases are:

```text
test_missing_authorization_header_is_401              PASSED
test_malformed_authorization_scheme_is_401            PASSED
test_unknown_token_is_401                             PASSED
test_valid_token_is_200                               PASSED
test_unconfigured_tokens_fail_closed_with_503         PASSED
test_empty_tokens_fail_closed_with_503                PASSED
test_malformed_token_entries_are_skipped              PASSED
test_conversation_owned_by_another_caller_is_404      PASSED
test_caller_can_continue_their_own_conversation       PASSED
test_exceeding_the_rate_limit_is_429_with_retry_after PASSED
test_rate_limit_is_per_caller                         PASSED
test_expired_rate_window_is_pruned                    PASSED
test_openai_content_filter_exception_maps_to_400      PASSED
test_content_filter_block_maps_to_400                 PASSED
test_content_filter_error_code_maps_to_400            PASSED
test_content_filter_error_wrapped_in_chain_maps_to_400 PASSED
test_content_filter_code_on_server_error_stays_502    PASSED
test_unrecognised_error_still_maps_to_502             PASSED
test_corpus_blob_target_returns_container_and_path    PASSED
test_corpus_blob_target_rejects_anything_outside_the_corpus (12 cases) PASSED
test_corpus_blob_target_without_a_configured_account_is_none PASSED
```

`test_corpus_blob_target_rejects_anything_outside_the_corpus` is parametrised over
a lookalike host, a different account, a different container, a non-URL, an empty
string, a container root, dot segments, a non-https scheme and a URL carrying a
query string.

### 2. Live checks against the deployed resources

Run with `DefaultAzureCredential`. These are observations, not simulations.

| Check | Observed |
| --- | --- |
| Policy stored in Azure | `strict-guardrail`, `base=Microsoft.DefaultV2`, `mode=Blocking`, 16 filters |
| Binary filters | `severityThreshold` absent on all 8 after the fix |
| Deployment binding | `raiPolicyName: strict-guardrail` on the chat model deployment |
| Direct call, jailbreak prompt | **HTTP 400**, `error.code: content_filter` |
| Agent path, jailbreak prompt | raised `OpenAIContentFilterException` |
| Gateway classification of that exception | classified as a content filter, so the client receives **400** |
| Harm-category prompts | `severity: safe` on all four categories — correctly not blocked |
| Browser | the frontend displayed the content-safety message for a jailbreak attempt |

The last row is the end-to-end proof: the same block reaches a user through the
frontend as a readable sentence rather than a generic failure.

## Known limitations and open items

- **The session store grows without bound.** The rate limiter prunes expired
  windows, but `SESSIONS` has no eviction and no per-caller cap.
- **The rate limiter is per-process and in-memory.** Restarting the API resets
  every counter and running more than one process grants each the full quota.
- **The frontend token is inlined into the browser bundle.** It authenticates the
  gateway against anonymous callers; it is not a secret from anyone who loads the
  page. A server-side proxy route is the correct fix.
- **The `Indirect Attack` filter is declared but expected to be inert.** Its
  document-level detection requires the caller to tag content as a document, and
  this application sends a bare message. It is declared for completeness, not as a
  working control.
- **Caller tokens are static.** There is no rotation, expiry or revocation.
- **API tokens are compared against a plaintext value in `.env`.** Acceptable at
  this scale; a secret store is the correct home for anything else.

## What this gate does not cover

- **No network controls.** No private endpoints, firewall rules or IP
  restrictions. Out of scope by explicit decision.
- **No data retention policy.** Out of scope by explicit decision.
- **No access audit trail.** Deferred.
- **No prompt-injection defense for retrieved content.** Phase 10.
- **No security evaluation suite.** The grounding probes are a regression check,
  not a security evaluation. Phase 11.
- **No metrics, alerting or correlation.** Phase 12.
- **No CI validation of the Terraform.** Phase 13.
- **No penetration testing, no dependency scanning and no accessibility or
  abuse-rate testing.**

## Acceptance

The Phase 9 exit criteria are met. Authentication fails closed and is covered by
contract tests; a conversation cannot be continued by another caller; a
Responsible AI guardrail is attached to the model deployment and was observed
blocking a real jailbreak through the agent and through the browser; credentials
remain externalized and the working tree is free of them; and every known risk is
recorded above with a control and a disposition.

Two properties were established by measurement and would otherwise have been
assumed: a severity threshold on a binary filter disables it, and the agent
inherits its deployment's guardrail without declaring one.

Phase 10 and Phase 11 are the natural successors. Neither is started.
