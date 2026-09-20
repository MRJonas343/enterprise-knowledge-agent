#!/usr/bin/env python3
"""Run the grounding probes against the deployed Foundry agent.

Runnable form of the four adversarial probes recorded in
docs/verification/phase-2-retrieval-acceptance.md. Not a pytest test: it makes
live Azure calls and is run explicitly.

    uv run python tests/run_probes.py [--only ID] [--json PATH]

Each probe uses a fresh conversation. Exit code is 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from enterprise_knowledge_agent.run_agent import AGENT_CONFIG, ROOT, load_settings

logging.getLogger("agent_framework").setLevel(logging.ERROR)
_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _reconfigure is not None:  # Windows cp1252 cannot print the agent's markers.
    _reconfigure(encoding="utf-8", errors="replace")

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "grounding-probes.yaml"
KNOWLEDGE_ROOT = ROOT / "enterprise-knowledge"
BLOB_CONTAINER = "enterprise-knowledge"

# Markers observed in this project's answers when the corpus does not answer the
# question. Matched case-insensitively; extend freely.
REFUSAL_MARKERS = (
    "could not find", "couldn't find", "not documented", "no information",
    "not enough information", "does not describe", "not described", "no documented",
)

# Attribution radius, in characters, for not_confident_about: a forbidden value
# is treated as attached to the nearest service name within this distance.
PROXIMITY_WINDOW = 120

# Service-name shape used to decide what a value is attributed to. The
# cross-service probe asks about a service, so the subject matches this.
SERVICE_TOKEN = re.compile(r"[a-z0-9][a-z0-9-]*-service")

# Negations that separate a value from the subject when they sit between the two
# ("is not documented for order-service", "the 50 is not order-service"). A value
# the answer denies for the subject is not an assertion about the subject.
DISSOCIATION_MARKERS = (
    "is not", "are not", "was not", "were not", "isn't", "aren't",
    "does not", "do not", "doesn't", "don't", "did not", "didn't",
    "cannot", "can't", "couldn't",
    "not stated", "not documented", "not described", "not specified",
    "not provided", "not given", "not listed", "not available",
    "without", "no documented", "no connection", "no pool",
)


def citation_urls(data) -> list[str]:
    """Every citation URL, one per annotated region (mirrors api.py)."""
    if isinstance(data, dict):
        if data.get("type") == "citation":
            url = data.get("url", "")
            regions = data.get("annotated_regions") or []
            return [url] * len(regions) if regions else ([url] if url else [])
        return [u for value in data.values() for u in citation_urls(value)]
    if isinstance(data, list):
        return [u for item in data for u in citation_urls(item)]
    return []


def check_refuses(answer, urls):
    for marker in REFUSAL_MARKERS:
        if marker in answer.lower():
            return True, f'matched refusal marker "{marker}"'
    return False, "no refusal marker found"


def check_zero_citations(answer, urls):
    if urls:
        return False, f"answer carries {len(urls)} citation(s)"
    return True, "answer carries no citations"


def check_citations_resolve(answer, urls):
    missing = []
    for url in urls:
        parts = url.split(f"/{BLOB_CONTAINER}/", 1)
        relative = unquote(parts[1].split("?", 1)[0]) if len(parts) == 2 else ""
        if not relative or not (KNOWLEDGE_ROOT / relative).is_file():
            missing.append(url)
    if missing:
        return False, "does not resolve to a file on disk: " + ", ".join(missing)
    return True, f"all {len(urls)} citation(s) resolve on disk" if urls else "no citations"


def _indices(haystack: str, needle: str) -> list[int]:
    positions, start = [], 0
    while (index := haystack.find(needle, start)) != -1:
        positions.append(index)
        start = index + len(needle)
    return positions


def check_not_confident_about(answer, urls, values, near):
    """Fail when a forbidden value is attributed to the probe's subject.

    A plain substring test is WRONG. The correct cross-service-contamination
    answer deliberately mentions "50": it says order-service's pool size is not
    documented and separately notes payment-service's pool of 50 per pod. The
    value appearing is CORRECT, so forbidding the string outright would fail
    exactly when the agent gets it right. Three recorded live runs each returned
    a correct answer that a raw proximity test still failed, because the number
    sat within 120 characters of an unrelated mention of `order-service`.

    So the check asks the actual question: what is the value attributed to? For
    each forbidden value it finds the nearest "<name>-service" token within
    PROXIMITY_WINDOW. A different service means the value is attributed
    elsewhere and passes. The subject means the value is being asserted about
    the subject, which fails unless a DISSOCIATION_MARKER sits between the two.
    Without `near`, it falls back to a plain must-not-appear-anywhere check. Do
    not "simplify" this into a substring or raw proximity test.

    Known limit: the between-marker test is lexical, so "order-service does not
    use PgBouncer; its pool size is 50" has a negation between subject and value
    and would pass. Regression check, not proof.
    """
    low = answer.lower()
    if not near:
        for value in values:
            if str(value).lower() in low:
                return False, f'forbidden value "{value}" appears in the answer'
        return True, "no forbidden value present"

    subject = near.lower()
    tokens = [(match.start(), match.group()) for match in SERVICE_TOKEN.finditer(low)]
    if not SERVICE_TOKEN.fullmatch(subject):
        # A non-service subject has no service token, so use its occurrences.
        tokens = [(index, subject) for index in _indices(low, subject)]

    for value in values:
        needle = str(value).lower()
        for position in _indices(low, needle):
            local = [
                (pos, name)
                for pos, name in tokens
                if abs(pos - position) <= PROXIMITY_WINDOW
            ]
            if not local:
                continue
            pos, name = min(local, key=lambda token: abs(token[0] - position))
            if name != subject:
                continue  # the value is attributed to a different service
            if pos < position:
                between = low[pos + len(name) : position]
            else:
                between = low[position + len(needle) : pos]
            if not any(marker in between for marker in DISSOCIATION_MARKERS):
                return False, (
                    f'forbidden value "{value}" is attributed to "{near}" '
                    f"with no negation between them"
                )
    return True, "no forbidden value asserted about the subject"


CHECKERS = {
    "refuses": check_refuses,
    "zero_citations": check_zero_citations,
    "citations_resolve": check_citations_resolve,
}


def evaluate(probe, answer, urls):
    results = []
    for check in probe.get("checks") or []:
        kind = check["kind"]
        if kind == "not_confident_about":
            passed, reason = check_not_confident_about(
                answer, urls, check.get("values") or [], check.get("near")
            )
        elif kind in CHECKERS:
            passed, reason = CHECKERS[kind](answer, urls)
        else:
            passed, reason = False, f"unknown check kind: {kind}"
        results.append({"kind": kind, "passed": passed, "reason": reason})
    return results


def resolve_agent_name() -> str:
    # Same resolution as run_agent.main: AZURE_AGENT_NAME, then agent_config.yaml.
    name = load_settings()["agent_name"]
    if not name and AGENT_CONFIG.is_file():
        config = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8")) or {}
        name = config.get("agent_name", "")
    return name


async def run(probes, json_path):
    agent = FoundryAgent(
        project_endpoint=load_settings()["project_endpoint"],
        agent_name=resolve_agent_name(),
        credential=DefaultAzureCredential(),
    )
    entries = []
    for probe in probes:
        print(f"\nRunning probe: {probe['id']} ...", flush=True)
        session = await agent.create_conversation()  # fresh conversation per probe
        result = await agent.run(probe["question"], session=session)
        answer = result.text or ""
        urls = citation_urls(result.to_dict())
        checks = evaluate(probe, answer, urls)
        entry = {
            "id": probe["id"],
            "question": probe["question"],
            "answer": answer,
            "citations": urls,
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
    print(f"\nResult: {passed}/{len(entries)} probes passed")
    for entry in entries:
        if not entry["passed"]:
            failed = [c["kind"] for c in entry["checks"] if not c["passed"]]
            print(f"  FAILED {entry['id']}: {', '.join(failed)}")

    if json_path:
        Path(json_path).write_text(
            json.dumps(
                {
                    "agent": resolve_agent_name(),
                    "passed": passed == len(entries),
                    "summary": {"passed": passed, "total": len(entries)},
                    "probes": entries,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {json_path}")
    return 0 if passed == len(entries) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the grounding probes.")
    parser.add_argument("--only", help="run a single probe by id")
    parser.add_argument("--json", dest="json_path", help="write results as JSON")
    args = parser.parse_args()

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

    probes = (yaml.safe_load(FIXTURE.read_text(encoding="utf-8")) or {}).get("probes") or []
    if args.only:
        probes = [probe for probe in probes if probe["id"] == args.only]
        if not probes:
            print(f"error: no probe with id {args.only!r}", file=sys.stderr)
            return 2

    try:
        return asyncio.run(run(probes, args.json_path))
    except (KeyboardInterrupt, asyncio.CancelledError):
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
