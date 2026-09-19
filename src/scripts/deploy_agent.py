#!/usr/bin/env python3
"""Deploy the Foundry agent that answers from the knowledge base over MCP.

Creates or updates two things:

1. A ``RemoteTool`` project connection that targets the MCP endpoint of the
   knowledge base and authenticates with the project's managed identity. It is a
   project resource on Azure Resource Manager, so it goes through a REST call
   because the projects SDK has no surface for it.
2. An agent version whose only tool is that knowledge base.

Configuration comes from .env. The agent name and system prompt come from
``agent_config.yaml`` next to this script.

Usage:
    uv run python src/scripts/deploy_agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).with_name("agent_config.yaml")

ARM_API_VERSION = "2025-10-01-preview"
MCP_API_VERSION = "2026-08-01-preview"

# Azure AI Search knowledge bases expose exactly one MCP tool today.
MCP_TOOL_NAME = "knowledge_base_retrieve"

REQUIRED = ("project_endpoint", "project_resource_id", "search_endpoint", "model")


def load_config() -> dict[str, str]:
    get = os.environ.get
    return {
        "project_endpoint": get("AZURE_PROJECT_ENDPOINT", "").rstrip("/"),
        "project_resource_id": get("AZURE_PROJECT_RESOURCE_ID", "").rstrip("/"),
        "connection_name": get("AZURE_PROJECT_CONNECTION_NAME", "knowledge-base-mcp"),
        "search_endpoint": get("AZURE_SEARCH_ENDPOINT", "").rstrip("/"),
        "knowledge_base": get("AZURE_KNOWLEDGE_BASE_NAME", "enterprise-knowledge-base"),
        "model": get("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
    }


def mcp_endpoint_for(cfg: dict[str, str]) -> str:
    return (
        f"{cfg['search_endpoint']}/knowledgebases/{cfg['knowledge_base']}"
        f"/mcp?api-version={MCP_API_VERSION}"
    )


def ensure_connection(cfg: dict[str, str], mcp_endpoint: str, credential) -> str:
    """Create or update the RemoteTool connection and return its ARM ID.

    The agent resolves the connection by ID at runtime, so return that rather
    than the bare name.
    """
    token = get_bearer_token_provider(
        credential, "https://management.azure.com/.default"
    )()
    url = (
        f"https://management.azure.com{cfg['project_resource_id']}"
        f"/connections/{cfg['connection_name']}?api-version={ARM_API_VERSION}"
    )

    response = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": cfg["connection_name"],
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ProjectManagedIdentity",
                "category": "RemoteTool",
                "target": mcp_endpoint,
                "isSharedToAll": True,
                "audience": "https://search.azure.com/",
                "metadata": {"ApiType": "Azure"},
            },
        },
        timeout=60,
    )
    response.raise_for_status()

    print(f"  connection '{cfg['connection_name']}' created or updated")
    return response.json()["id"]


def main() -> int:
    load_dotenv(ROOT / ".env")
    cfg = load_config()

    missing = [key for key in REQUIRED if not cfg[key]]
    if missing:
        print(f"error: missing {', '.join(missing)} in .env", file=sys.stderr)
        return 2

    if not CONFIG_PATH.is_file():
        print(f"error: {CONFIG_PATH} not found", file=sys.stderr)
        return 2

    agent_cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    agent_name = agent_cfg.get("agent_name")
    instructions = agent_cfg.get("system_prompt")
    if not agent_name or not instructions:
        print(
            f"error: {CONFIG_PATH.name} needs both agent_name and system_prompt",
            file=sys.stderr,
        )
        return 2

    mcp_endpoint = mcp_endpoint_for(cfg)
    credential = DefaultAzureCredential()

    try:
        connection_id = ensure_connection(cfg, mcp_endpoint, credential)

        tool = MCPTool(
            server_label="knowledge-base",
            server_url=mcp_endpoint,
            require_approval="never",
            allowed_tools=[MCP_TOOL_NAME],
            project_connection_id=connection_id,
        )

        with AIProjectClient(endpoint=cfg["project_endpoint"], credential=credential) as client:
            agent = client.agents.create_version(
                agent_name=agent_name,
                definition=PromptAgentDefinition(
                    model=cfg["model"],
                    instructions=instructions,
                    tools=[tool],
                ),
            )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"  agent '{agent.name}' version {agent.version} deployed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
