#!/usr/bin/env python3
"""Run the grounding probes against the deployed Foundry agent.

A thin wrapper over the shared evaluation runner (tests/run_evaluations.py): the
probes fixture carries the four adversarial probes recorded in
docs/verification/phase-2-retrieval-acceptance.md, and the checks live in
tests/eval_checks.py. The CLI, the console output and the JSON shape are the
ones the documentation already points at.

    uv run python tests/run_probes.py [--only ID] [--json PATH]

Each probe uses a fresh conversation. Exit code is 0 only if every check passes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import run_evaluations

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "grounding-probes.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the grounding probes.")
    parser.add_argument("--only", help="run a single probe by id")
    parser.add_argument("--json", dest="json_path", help="write results as JSON")
    args = parser.parse_args()

    return run_evaluations.run_fixture(
        FIXTURE,
        only=args.only,
        json_path=args.json_path,
        noun="probe",
        list_key="probes",
    )


if __name__ == "__main__":
    raise SystemExit(main())
