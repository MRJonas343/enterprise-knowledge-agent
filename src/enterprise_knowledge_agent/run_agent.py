#!/usr/bin/env python3
"""Run the deployed agent interactively from the terminal.

The agent's only tool is the knowledge base, and Foundry Agent Service executes
it server side, so no local tools are passed here. This script is just a thin
client: it opens a conversation and prints the grounded answers.

The agent name comes from agent_config.yaml so it cannot drift from what
deploy_agent.py publishes. The project endpoint comes from .env.

Usage:
    uv run python -m enterprise_knowledge_agent.run_agent
    uv run python src/enterprise_knowledge_agent/run_agent.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

logging.getLogger("agent_framework").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[2]
AGENT_CONFIG = ROOT / "src" / "scripts" / "agent_config.yaml"


def load_settings() -> dict[str, str]:
    get = os.environ.get
    return {
        "project_endpoint": get("AZURE_PROJECT_ENDPOINT", "").rstrip("/"),
        "agent_name": get("AZURE_AGENT_NAME", ""),
    }


async def chat(agent: FoundryAgent) -> None:
    session = await agent.create_conversation()
    print("Grounded answers over the Aurora Commerce knowledge base.")
    print("Type 'exit' to stop.\n")

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not message or message.lower() in ("exit", "quit"):
            break

        try:
            result = await agent.run(message, session=session)
            print(f"\nAgent: {result.text}\n")
        except Exception as exc:
            print(f"\nerror: {exc}\n", file=sys.stderr)


def main() -> int:
    load_dotenv(ROOT / ".env")
    settings = load_settings()

    if not settings["project_endpoint"]:
        print("error: missing AZURE_PROJECT_ENDPOINT in .env", file=sys.stderr)
        return 2

    if not settings["agent_name"]:
        if not AGENT_CONFIG.is_file():
            print(f"error: {AGENT_CONFIG} not found", file=sys.stderr)
            return 2
        agent_cfg = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8")) or {}
        settings["agent_name"] = agent_cfg.get("agent_name", "")

    if not settings["agent_name"]:
        print(
            "error: agent name not found. Set AZURE_AGENT_NAME or add agent_name "
            f"to {AGENT_CONFIG.name}.",
            file=sys.stderr,
        )
        return 2

    agent = FoundryAgent(
        project_endpoint=settings["project_endpoint"],
        agent_name=settings["agent_name"],
        credential=DefaultAzureCredential(),
    )

    try:
        asyncio.run(chat(agent))
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Ctrl+C is delivered to the running event loop rather than to the
        # input() call, so it surfaces here as a cancellation. Exit quietly.
        print()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
