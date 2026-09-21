# Phase 11 Evaluations Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-20 |
| Phase | Phase 11, Evaluations |
| Environment | Local run against the deployed `canadacentral` agent |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 11 exit criteria are:

> Evaluation evidence is reproducible; known failures are tracked; changes are
> compared with baselines before release.

All three are met, and the "known failures" clause is met by a real defect rather
than by an empty list.

## Scope

Tier 1 only: deterministic evaluation. There is **no LLM judge**, and no
`azure-ai-evaluation` dependency.

That is possible because the corpus is version-controlled and local. For every
value an answer asserts, the harness can check whether the document the answer
cited actually contains it. A value present in an uncited document but missing
from the cited one is a hallucination, and it is detectable without a model.

Relevance scoring and any judge-based metric are out of scope and recorded as
such in the roadmap.

## What was built

| File | Role |
| --- | --- |
| `tests/eval_checks.py` | Every checker, as pure functions. No Azure, no network. Being pure is what makes them unit-testable in CI. |
| `tests/run_evaluations.py` | The runner: per-case latency and token use, `--save-baseline`, `--compare-baseline`. |
| `tests/fixtures/evaluation-cases.yaml` | Ten factual cases. Every expected value is drawn from an actual corpus document. |
| `tests/test_eval_checks.py` | 42 unit tests over the checkers. Collected by pytest, so they run in CI. |
| `tests/run_probes.py` | Reduced to a thin wrapper over the shared runner. Its CLI and JSON output are unchanged, so the documented command still works. |

The check vocabulary, all deterministic:

| Check | What it verifies |
| --- | --- |
| `source_supports_claim` | Each value the answer asserts appears in at least one document it cited. |
| `cites_document` | The answer cites the expected source, not a lookalike. |
| `answer_contains` | The expected values are present. |
| `markers_match_spans` | Every annotation span slices an inline marker out of the answer, and every marker is covered by a span. This checks the citation contract against the live service, not against a fake. |
| `not_contains` | Used for injection canaries. |
| `refuses`, `zero_citations`, `citations_resolve`, `not_confident_about` | Carried over from the grounding probes unchanged. |

## Evidence

### 1. The baseline

Recorded on 2026-09-20 against `aurora-knowledge-agent` and committed as
`tests/baseline.json`.

```text
9 of 10 cases passed

latency per case   4 302 ms to 8 584 ms, 53.8 s total
input tokens       ~61 500 across the ten cases
output tokens      ~1 270 across the ten cases
```

The input figure is dominated by retrieved context, roughly 6 000 tokens per
case. That is the measurement the Phase 6 retrieval-effort question would move,
and it is recorded here so the comparison has a starting point.

### 2. The checkers are exercised in CI

```text
42 passed in 0.10s
```

The whole suite is 90 tests, from 48 before this phase. The evaluation runner
itself is not run in CI, because it needs live Azure and CI has no credentials.

### 3. Every expected value is a real value

Each value in `tests/fixtures/evaluation-cases.yaml` was confirmed against the
document it is attributed to before being written. A fixture with a guessed
value would be worse than no fixture, because it would report a failure that is
the harness's fault rather than the agent's.

## Known failure: `runbook-index-command`

**Recorded, not fixed, and deliberately not deleted.**

The question asks which index the database latency runbook creates on the
settlements table. The answer is correct — `idx_settlements_date_status`, on
`settlements (settlement_date, status)` — and it even opens with "The runbook
creates".

The two documents it cites are `architecture/payment-service.md` and
`incidents/INC-2026-003.md`. Neither contains the index name:

- `payment-service.md` discusses "the missing index on the settlement filter
  columns" without naming it.
- `INC-2026-003.md` lists "Add the missing index on the reporting query filter
  columns" as an action item, also without naming it.

The name appears in exactly one place in the corpus,
`runbooks/database-latency.md:96`. The answer is grounded; its provenance is
wrong. A reader following those citations would not find the claim.

The failure split is the diagnosis: `answer_contains` passes while
`cites_document` and `source_supports_claim` fail. Right answer, unsupported
provenance.

It is recorded rather than repaired because the system prompt already instructs
the agent to attribute each factual claim to the document it came from, so this
is model behaviour on a question where several documents discuss the same
subject without naming the specific artefact. Changing it would need prompt work
and a fresh measurement. Deleting the case would delete the only signal the
suite produced on its first run.

## Known limitations and open items

- **The suite is small.** Ten cases, four adversarial probes. It is a regression
  check, not a benchmark.
- **`answer_contains` matches the corpus's own wording.** A correct paraphrase
  such as "18-minute" instead of "18 minutes" fails the check. That is a real
  signal to review, not a fixture error, but it is a false-negative source.
- **No relevance or retrieval-quality metric.** Both would need a judge or
  retrieval-level instrumentation. Out of scope.
- **No per-document attribution score.** The harness reports pass or fail, not a
  proportion.
- **Latency is a single sample per case.** No percentiles, no repetition, so it
  cannot separate a real change from run-to-run noise.
- **The suite needs live Azure**, so it cannot gate a merge.
- **Two experiments the harness enables have not been run**, because both are
  operational rather than code. The retrieval reasoning effort is fixed when the
  knowledge base is created, so comparing settings means recreating it per
  setting and re-ingesting the corpus. The poisoned-document case needs a
  document added to the corpus and the knowledge base rebuilt.

## What this gate does not cover

- **No groundedness judge.** Deliberate; see Scope.
- **No prompt-injection run.** The `not_contains` check and the carrying
  poisoned-document criterion exist, but the experiment has not been run.
- **No retrieval-effort comparison.** The capability exists; the runs do not.
- **No dashboard, trend or historical record.** The baseline is a JSON file.
- **No cost accounting beyond token counts.** No price model is applied.

## Acceptance

The Phase 11 exit criteria are met. The evidence is reproducible: the fixtures,
the checkers and the baseline are all in version control, and the recorded
baseline is a committed file. Known failures are tracked, with one recorded in
full above. Changes are compared with baselines through `--compare-baseline`,
which reports per-case deltas and exits non-zero on a pass-to-fail regression.

The suite is accepted with a failing case. A ten-out-of-ten first run would say
more about the fixtures than about the agent.
