#!/usr/bin/env python3
"""Link an Application Insights resource to the Foundry project for tracing.

Creates or updates one project connection of category ``AppInsights``, against
the same ARM endpoint ``deploy_agent.py`` uses. Only the category and the target
differ: the target is the Application Insights resource ID, not an MCP endpoint.

This is keyless. The Application Insights resource has local authentication
disabled, and the Foundry project identity reaches it through the Monitoring
Metrics Publisher role assigned in ``infra/terraform/tracing.tf``. No connection
string or instrumentation key is involved.

Azure allows only one AppInsights connection per project; a second fails with
"Multiple connection with same category (AppInsights) created". This is a PUT
against a fixed name, so re-running updates the existing connection rather than
creating another, which is the intended behaviour.

Configuration comes from .env.

Usage:
    uv run python src/scripts/link_tracing.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

ARM_API_VERSION = "2025-10-01-preview"

REQUIRED = ("project_resource_id", "app_insights_resource_id")


def load_config() -> dict[str, str]:
    get = os.environ.get
    return {
        "project_resource_id": get("AZURE_PROJECT_RESOURCE_ID", "").rstrip("/"),
        "app_insights_resource_id": get("AZURE_APP_INSIGHTS_RESOURCE_ID", "").rstrip("/"),
        "connection_name": get("AZURE_TRACING_CONNECTION_NAME", "app-insights"),
    }


def main() -> int:
    load_dotenv(ROOT / ".env")
    cfg = load_config()

    missing = [key for key in REQUIRED if not cfg[key]]
    if missing:
        print(f"error: missing {', '.join(missing)} in .env", file=sys.stderr)
        return 2

    url = (
        f"https://management.azure.com{cfg['project_resource_id']}"
        f"/connections/{cfg['connection_name']}?api-version={ARM_API_VERSION}"
    )

    try:
        token = get_bearer_token_provider(
            DefaultAzureCredential(), "https://management.azure.com/.default"
        )()
        # Fixed name: this PUT updates the single allowed connection, not a second.
        response = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": cfg["connection_name"],
                "type": "Microsoft.MachineLearningServices/workspaces/connections",
                "properties": {
                    "authType": "ProjectManagedIdentity",
                    "category": "AppInsights",
                    "target": cfg["app_insights_resource_id"],
                    "isSharedToAll": True,
                    "metadata": {"ApiType": "Azure"},
                },
            },
            timeout=60,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"  connection '{cfg['connection_name']}' linked to Application Insights "
        f"'{cfg['app_insights_resource_id']}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
