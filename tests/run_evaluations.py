#!/usr/bin/env python3
"""Run deterministic evaluations against the deployed Foundry agent.

The checks themselves are pure and live in tests/eval_checks.py; they verify an
answer and its citations against the version-controlled corpus under
enterprise-knowledge/ instead of asking a model to judge grounding. This runner
only adds the live part: one fresh conversation per case, the agent call, wall
clock timing, optional token usage, and comparison against a saved baseline.
Tier 2 (an LLM judge) is deliberately out of scope.

    uv run python tests/run_evaluations.py [--fixture PATH] [--only ID] [--json PATH]
                                           [--save-baseline PATH] [--compare-baseline PATH]

--fixture defaults to tests/fixtures/evaluation-cases.yaml. The fixture list key
is `cases`; `probes` is accepted too so tests/fixtures/grounding-probes.yaml
loads unchanged. Exit code is 0 only when every case passes, or when a baseline
comparison shows no regression; 2 is a configuration error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from enterprise_knowledge_agent.run_agent import AGENT_CONFIG, ROOT, load_settings

from eval_checks import citation_spans, citation_urls, evaluate

logging.getLogger("agent_framework").setLevel(logging.ERROR)
_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _reconfigure is not None:  # Windows cp1252 cannot print the agent's markers.
    _reconfigure(encoding="utf-8", errors="replace")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "evaluation-cases.yaml"


def resolve_agent_name() -> str:
    # Same resolution as run_agent.main: AZURE_AGENT_NAME, then agent_config.yaml.
    name = load_settings()["agent_name"]
    if not name and AGENT_CONFIG.is_file():
        config = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8")) or {}
        name = config.get("agent_name", "")
    return name


def load_fixture(path) -> list[dict]:
    """Load a fixture's case list.

    New fixtures use the `cases` key; the grounding probes use `probes`. Both
    are accepted so the probes fixture loads without a rewrite.
    """
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for key in ("cases", "probes"):
        if key in document:
            return document[key] or []
    raise ValueError(f"{path} has neither a 'cases' nor a 'probes' key")


def _usage_details(result) -> dict | None:
    """Return the provider's token usage verbatim, or None when it is absent.

    The framework exposes usage_details only when the service returned it. Never
    estimate or synthesise counts: null records that the response carried no
    usage, which is a fact about the service, not a gap to fill in.
    """
    usage = getattr(result, "usage_details", None)
    if not usage:
        return None
    try:
        return dict(usage)
    except (TypeError, ValueError):
        return None


def _payload(entries, passed, list_key) -> dict[str, Any]:
    return {
        "agent": resolve_agent_name(),
        "passed": passed == len(entries),
        "summary": {"passed": passed, "total": len(entries)},
        list_key: entries,
    }


def _write_run(path, payload) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def _load_baseline(path) -> tuple[dict | None, str | None]:
    """Parse a saved baseline, returning (document, error message)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"cannot read baseline {path}: {exc}"
    except ValueError as exc:
        return None, f"baseline {path} is not valid JSON: {exc}"


def _compare(entries, baseline, label, noun) -> int:
    previous = {
        entry.get("id"): entry
        for entry in baseline.get("cases") or baseline.get("probes") or []
    }

    regressed: list[str] = []
    improved: list[str] = []
    latencies: list[tuple[str, int, int]] = []
    for entry in entries:
        prior = previous.get(entry["id"])
        if prior is None:
            continue  # a case with no baseline entry has nothing to regress from
        was, now = bool(prior.get("passed")), bool(entry["passed"])
        if was and not now:
            regressed.append(entry["id"])
        elif not was and now:
            improved.append(entry["id"])
        before, after = prior.get("latency_ms"), entry.get("latency_ms")
        if isinstance(before, int) and isinstance(after, int):
            latencies.append((entry["id"], before, after))

    print(f"\nBaseline comparison against {label}:")
    print(f"  newly failing: {', '.join(regressed) if regressed else 'none'}")
    print(f"  newly passing: {', '.join(improved) if improved else 'none'}")
    if latencies:
        print("  latency change:")
        for case_id, before, after in latencies:
            delta = after - before
            sign = "+" if delta >= 0 else ""
            print(f"    {case_id}: {before} ms -> {after} ms ({sign}{delta} ms)")
    else:
        print("  latency change: no comparable latency in the baseline")

    if regressed:
        print(f"  REGRESSION: {len(regressed)} {noun}(s) went from pass to fail")
        return 1
    print("  no regression")
    return 0


async def run(
    cases,
    *,
    json_path=None,
    save_baseline=None,
    baseline=None,
    baseline_path=None,
    noun="case",
    list_key="cases",
    agent=None,
) -> int:
    if agent is None:
        agent = FoundryAgent(
            project_endpoint=load_settings()["project_endpoint"],
            agent_name=resolve_agent_name(),
            credential=DefaultAzureCredential(),
        )

    entries: list[dict[str, Any]] = []
    for case in cases:
        print(f"\nRunning {noun}: {case['id']} ...", flush=True)
        session = await agent.create_conversation()  # fresh conversation per case
        started = time.perf_counter()
        result = await agent.run(case["question"], session=session)
        latency_ms = round((time.perf_counter() - started) * 1000)

        data = result.to_dict()
        answer = result.text or ""
        urls = citation_urls(data)
        spans = citation_spans(data)
        checks = evaluate(case, answer, urls, spans)
        entry = {
            "id": case["id"],
            "question": case["question"],
            "answer": answer,
            "citations": urls,
            "latency_ms": latency_ms,
            "usage_details": _usage_details(result),
            "checks": checks,
            "passed": all(check["passed"] for check in checks),
        }
        entries.append(entry)

        print(f"\n=== {entry['id']} ===")
        print(f"Q: {entry['question']}")
        print(f"Answer ({len(answer)} chars):\n{answer}")
        print(f"Citations: {len(urls)}")
        for check in checks:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"  [{mark}] {check['kind']} — {check['reason']}")

    passed = sum(1 for entry in entries if entry["passed"])
    print(f"\nResult: {passed}/{len(entries)} {noun}s passed")
    for entry in entries:
        if not entry["passed"]:
            failed = [c["kind"] for c in entry["checks"] if not c["passed"]]
            print(f"  FAILED {entry['id']}: {', '.join(failed)}")

    if json_path:
        _write_run(json_path, _payload(entries, passed, list_key))
    if save_baseline:
        _write_run(save_baseline, _payload(entries, passed, list_key))

    if baseline is not None:
        return _compare(entries, baseline, baseline_path, noun)
    return 0 if passed == len(entries) else 1


def run_fixture(
    fixture,
    *,
    only=None,
    json_path=None,
    save_baseline=None,
    compare_baseline=None,
    noun="case",
    list_key="cases",
) -> int:
    """Load a fixture, validate configuration, and run it. Shared by both CLIs."""
    load_dotenv(ROOT / ".env")
    if not load_settings()["project_endpoint"]:
        print("error: missing AZURE_PROJECT_ENDPOINT in .env", file=sys.stderr)
        return 2
    if not resolve_agent_name():
        print(
            f"error: agent name not found. Set AZURE_AGENT_NAME or add agent_name "
            f"to {AGENT_CONFIG.name}.",
            file=sys.stderr,
        )
        return 2

    try:
        cases = load_fixture(fixture)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"error: cannot load fixture {fixture}: {exc}", file=sys.stderr)
        return 2

    if only:
        cases = [case for case in cases if case["id"] == only]
        if not cases:
            print(f"error: no {noun} with id {only!r}", file=sys.stderr)
            return 2

    baseline = None
    if compare_baseline:
        baseline, error = _load_baseline(compare_baseline)
        if error:
            print(f"error: {error}", file=sys.stderr)
            return 2

    try:
        return asyncio.run(
            run(
                cases,
                json_path=json_path,
                save_baseline=save_baseline,
                baseline=baseline,
                baseline_path=compare_baseline,
                noun=noun,
                list_key=list_key,
            )
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        print()
        return 130


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic evaluations against the Foundry agent."
    )
    parser.add_argument(
        "--fixture",
        default=str(FIXTURE),
        help="path to a fixture (default: tests/fixtures/evaluation-cases.yaml)",
    )
    parser.add_argument("--only", help="run a single case by id")
    parser.add_argument("--json", dest="json_path", help="write results as JSON")
    parser.add_argument(
        "--save-baseline", dest="save_baseline", help="write the run as a baseline"
    )
    parser.add_argument(
        "--compare-baseline",
        dest="compare_baseline",
        help="compare against a previous run and report regressions",
    )
    args = parser.parse_args(argv)

    return run_fixture(
        args.fixture,
        only=args.only,
        json_path=args.json_path,
        save_baseline=args.save_baseline,
        compare_baseline=args.compare_baseline,
    )


if __name__ == "__main__":
    raise SystemExit(main())
