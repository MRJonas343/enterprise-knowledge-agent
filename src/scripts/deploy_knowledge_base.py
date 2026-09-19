#!/usr/bin/env python3
"""Create or update the Foundry IQ knowledge source and knowledge base.

Both are Azure AI Search data-plane objects, so they cannot be managed by
Terraform. Every call is create-or-update, so re-running the script is safe.

Configuration comes from .env. Run `terraform output` in infra/terraform for the
values.

Usage:
    uv run python src/scripts/deploy_knowledge_base.py
    uv run python src/scripts/deploy_knowledge_base.py --status
    uv run python src/scripts/deploy_knowledge_base.py --recreate

The embedding model, container and network mode are fixed when the knowledge
source is created. Changing any of them requires --recreate, which deletes the
knowledge base and the source, including the generated index, and re-ingests
every document.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureBlobKnowledgeSource,
    AzureBlobKnowledgeSourceParameters,
    AzureOpenAIVectorizerParameters,
    KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel,
    KnowledgeBaseRetrieveDefaults,
    KnowledgeSourceContentExtractionMode,
    KnowledgeSourceReference,
)
from azure.search.documents.knowledgebases.models import (
    KnowledgeRetrievalLowReasoningEffort,
    KnowledgeRetrievalOutputMode,
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceIngestionParameters,
    KnowledgeSourceNetworkAccessMode,
)
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

# Preview is required for query planning, output mode and configurable effort.
API_VERSION = "2026-08-01-preview"

REQUIRED = (
    "search",
    "storage_id",
    "foundry",
    "chat_deployment",
    "chat_model",
    "embedding_deployment",
    "embedding_model",
)


def load_config() -> dict[str, str]:
    get = os.environ.get
    return {
        "search": get("AZURE_SEARCH_ENDPOINT", ""),
        "storage_id": get("AZURE_STORAGE_ACCOUNT_RESOURCE_ID", ""),
        "foundry": get("AZURE_OPENAI_ENDPOINT", ""),
        "chat_deployment": get("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
        "chat_model": get("AZURE_OPENAI_CHAT_MODEL", ""),
        "embedding_deployment": get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""),
        "embedding_model": get("AZURE_OPENAI_EMBEDDING_MODEL", ""),
        "container": get("AZURE_KNOWLEDGE_CONTAINER", "enterprise-knowledge"),
        "source": get("AZURE_KNOWLEDGE_SOURCE_NAME", "enterprise-knowledge-source"),
        "base": get("AZURE_KNOWLEDGE_BASE_NAME", "enterprise-knowledge-base"),
    }


def params(cfg: dict[str, str], deployment: str, model: str) -> AzureOpenAIVectorizerParameters:
    return AzureOpenAIVectorizerParameters(
        resource_url=cfg["foundry"],
        deployment_name=cfg[deployment],
        model_name=cfg[model],
    )


def build_source(cfg: dict[str, str]) -> AzureBlobKnowledgeSource:
    """Point at the blob container. Foundry IQ generates the indexer pipeline."""
    return AzureBlobKnowledgeSource(
        name=cfg["source"],
        description="Version-controlled enterprise knowledge corpus.",
        azure_blob_parameters=AzureBlobKnowledgeSourceParameters(
            connection_string=f"ResourceId={cfg['storage_id']}",
            container_name=cfg["container"],
            is_adls_gen2=False,
            ingestion_parameters=KnowledgeSourceIngestionParameters(
                content_extraction_mode=KnowledgeSourceContentExtractionMode.MINIMAL,
                network_access_mode=KnowledgeSourceNetworkAccessMode.PUBLIC,
                embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
                    azure_open_ai_parameters=params(cfg, "embedding_deployment", "embedding_model")
                ),
                chat_completion_model=KnowledgeBaseAzureOpenAIModel(
                    azure_open_ai_parameters=params(cfg, "chat_deployment", "chat_model")
                ),
            ),
        ),
    )


def build_base(cfg: dict[str, str]) -> KnowledgeBase:
    """Reference the source and define retrieval behaviour."""
    return KnowledgeBase(
        name=cfg["base"],
        description="Grounded answers over internal documentation.",
        knowledge_sources=[KnowledgeSourceReference(name=cfg["source"])],
        models=[
            KnowledgeBaseAzureOpenAIModel(
                azure_open_ai_parameters=params(cfg, "chat_deployment", "chat_model")
            )
        ],
        output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
        retrieval_reasoning_effort=KnowledgeRetrievalLowReasoningEffort(),
        retrieve_defaults=KnowledgeBaseRetrieveDefaults(
            max_runtime_in_seconds=45,
            max_output_documents=8,
            max_output_size_in_tokens=12000,
        ),
    )


def report(client: SearchIndexClient, name: str, *, wait: bool, timeout: int = 900) -> int:
    """Print ingestion progress and any per-document errors. Returns 0 on success."""
    deadline = time.monotonic() + (timeout if wait else 0)

    while True:
        status = client.get_knowledge_source_status(name)
        last = status.last_synchronization_state
        current = status.current_synchronization_state

        if last and last.end_time:
            print(
                f"  indexed={last.items_updates_processed}"
                f" failed={last.items_updates_failed}"
                f" skipped={last.items_skipped}"
            )
            if not last.items_updates_failed:
                return 0

            errors = (current.errors if current else None) or []
            for error in errors:
                print(f"  [{error.status_code}] {error.doc_id}: {error.error_message}")
            if not errors:
                print(json.dumps(status.as_dict(), indent=2, default=str))
            return 1

        if current:
            print(f"  ingesting: processed={current.items_updates_processed} failed={current.items_updates_failed}")

        if time.monotonic() >= deadline:
            print("  still running; re-run with --status to check again")
            return 0

        time.sleep(10)


def delete_existing(client: SearchIndexClient, cfg: dict[str, str]) -> None:
    """Drop the knowledge base then the source.

    The base must go first because it references the source. Deleting the source
    also deletes the datasource, skillset, indexer and index it generated.
    """
    for label, name, delete in (
        ("base", cfg["base"], client.delete_knowledge_base),
        ("source", cfg["source"], client.delete_knowledge_source),
    ):
        try:
            delete(name)
            print(f"  deleted {label} '{name}'")
        except ResourceNotFoundError:
            print(f"  {label} '{name}' did not exist")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or update the Foundry IQ knowledge source and knowledge base."
    )
    parser.add_argument("--status", action="store_true", help="Only print ingestion status.")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for ingestion.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete the knowledge base and source first. Required to change the "
        "embedding model, container or network mode. Re-ingests everything.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    cfg = load_config()

    missing = [key for key in REQUIRED if not cfg[key]]
    if missing:
        print(f"error: missing {', '.join(missing)} in .env", file=sys.stderr)
        return 2

    if "/openai" in cfg["foundry"]:
        print(
            "error: AZURE_OPENAI_ENDPOINT must be the bare Foundry resource endpoint,\n"
            "       https://<name>.services.ai.azure.com, with no /openai/v1 suffix.\n"
            "       Use `terraform output ai_foundry_endpoint`.",
            file=sys.stderr,
        )
        return 2

    client = SearchIndexClient(cfg["search"], DefaultAzureCredential(), api_version=API_VERSION)

    try:
        if args.status:
            return report(client, cfg["source"], wait=False)

        if args.recreate:
            print("  recreating: the existing index and its content will be deleted")
            delete_existing(client, cfg)

        client.create_or_update_knowledge_source(build_source(cfg))
        print(f"  source '{cfg['source']}' created or updated")
        result = report(client, cfg["source"], wait=not args.no_wait)

        client.create_or_update_knowledge_base(build_base(cfg))
        print(f"  base   '{cfg['base']}' created or updated")
    except AzureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return result


if __name__ == "__main__":
    raise SystemExit(main())
