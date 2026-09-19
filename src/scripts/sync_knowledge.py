#!/usr/bin/env python3
"""Synchronize the version-controlled enterprise knowledge corpus to Blob Storage.

The Markdown under ``enterprise-knowledge/`` is the source of truth. This script
mirrors that folder into the Blob container that backs the Foundry IQ knowledge
source, preserving the folder structure and copying each document's metadata
table into Blob metadata so it can be filtered on later.

Authentication is keyless. It uses ``DefaultAzureCredential``, so the operator
running this script needs the *Storage Blob Data Contributor* role on the
storage account. No account key or connection string is used anywhere.

Usage:
    uv run python src/scripts/sync_knowledge.py --dry-run
    uv run python src/scripts/sync_knowledge.py --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "enterprise-knowledge"
DEFAULT_CONTAINER = "enterprise-knowledge"
CONTENT_TYPE = "text/markdown; charset=utf-8"
HASH_METADATA_KEY = "content_sha256"

# Maps the labels in each document's metadata table to Blob metadata keys.
METADATA_FIELDS = {
    "Document ID": "document_id",
    "Document type": "document_type",
    "Service": "service",
    "Team": "team",
    "Classification": "classification",
    "Last updated": "last_updated",
}

EXIT_OK = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2


class SyncError(RuntimeError):
    """Raised when the sync cannot run at all, as opposed to a single file failing."""


@dataclass
class SyncResult:
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.uploaded)


def parse_document_metadata(text: str) -> dict[str, str]:
    """Read the ``| Field | Value |`` table that follows the document title.

    Only the first table that starts with the ``Field``/``Value`` header is read,
    so metadata declared in later tables in the body cannot leak in.
    """
    metadata: dict[str, str] = {}
    inside_table = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not inside_table:
            if line == "| Field | Value |":
                inside_table = True
            continue

        if not line.startswith("|"):
            break

        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2:
            continue

        label, value = cells
        if label == "---":
            continue

        key = METADATA_FIELDS.get(label)
        if key is not None:
            metadata[key] = value

    return metadata


def sha256_of(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def discover_documents(source: Path) -> list[Path]:
    """Return every Markdown document under ``source``, in a stable order."""
    if not source.is_dir():
        raise SyncError(f"Source directory does not exist: {source}")

    return sorted(
        path
        for path in source.rglob("*.md")
        if path.is_file() and not path.name.startswith(".")
    )


def build_desired_metadata(path: Path, payload: bytes) -> dict[str, str]:
    """Combine the document's own metadata table with its content hash."""
    text = payload.decode("utf-8")
    metadata = parse_document_metadata(text)
    metadata[HASH_METADATA_KEY] = sha256_of(payload)

    for key, value in metadata.items():
        try:
            value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise SyncError(
                f"{path.name}: metadata value for '{key}' must be ASCII for Blob metadata"
            ) from exc

    return metadata


def normalize_metadata(metadata: dict[str, str] | None) -> dict[str, str]:
    """Blob metadata keys are case-insensitive; compare them lowercased."""
    if not metadata:
        return {}
    return {key.lower(): value for key, value in metadata.items()}


def sync(
    *,
    source: Path,
    container: str,
    account_name: str,
    dry_run: bool,
    force: bool,
    verbose: bool,
) -> SyncResult:
    account_url = f"https://{account_name}.blob.core.windows.net"
    result = SyncResult()

    try:
        service = BlobServiceClient(
            account_url=account_url, credential=DefaultAzureCredential()
        )
        container_client = service.get_container_client(container)

        if not dry_run and not container_client.exists():
            raise SyncError(
                f"Container '{container}' not found in {account_url}. "
                "Run terraform apply first, or pass --container."
            )

        remote = {
            blob.name: normalize_metadata(blob.metadata)
            for blob in container_client.list_blobs(include=["metadata"])
        }
    except SyncError:
        raise
    except AzureError as exc:
        raise SyncError(
            f"Could not reach {account_url}: {exc}. "
            "Confirm you are signed in with `az login` and that your identity has "
            "the Storage Blob Data Contributor role on the storage account."
        ) from exc

    documents = discover_documents(source)
    local_names: set[str] = set()

    for path in documents:
        blob_name = path.relative_to(source).as_posix()
        local_names.add(blob_name)

        try:
            payload = path.read_bytes()
            desired = build_desired_metadata(path, payload)
        except (OSError, UnicodeDecodeError, SyncError) as exc:
            result.failed.append((blob_name, str(exc)))
            continue

        if not force and remote.get(blob_name) == desired:
            result.skipped.append(blob_name)
            if verbose:
                print(f"  unchanged  {blob_name}")
            continue

        if dry_run:
            result.uploaded.append(blob_name)
            print(f"  would sync {blob_name}")
            continue

        try:
            container_client.upload_blob(
                name=blob_name,
                data=payload,
                overwrite=True,
                content_type=CONTENT_TYPE,
                metadata=desired,
            )
        except AzureError as exc:
            result.failed.append((blob_name, str(exc)))
            continue

        result.uploaded.append(blob_name)
        if verbose:
            print(f"  uploaded   {blob_name}")

    # Blobs with no local counterpart are reported, never deleted silently.
    result.orphaned = sorted(name for name in remote if name not in local_names)
    return result


def print_report(result: SyncResult, *, container: str, account: str, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "SYNC"
    print()
    print(f"[{mode}] {container} @ {account}.blob.core.windows.net")
    print(f"  uploaded  {len(result.uploaded)}")
    print(f"  unchanged {len(result.skipped)}")
    print(f"  failed    {len(result.failed)}")

    if result.failed:
        print()
        print("Failures:")
        for name, message in result.failed:
            print(f"  {name}: {message}")

    if result.orphaned:
        print()
        print("In the container but not in the repository (not deleted):")
        for name in result.orphaned:
            print(f"  {name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize the enterprise knowledge Markdown corpus to Blob Storage."
    )
    parser.add_argument(
        "--account-name",
        default=os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", ""),
        help="Storage account name. Defaults to $AZURE_STORAGE_ACCOUNT_NAME.",
    )
    parser.add_argument(
        "--container",
        default=os.environ.get("AZURE_KNOWLEDGE_CONTAINER", DEFAULT_CONTAINER),
        help=f"Blob container name. Defaults to {DEFAULT_CONTAINER}.",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Local corpus folder. Defaults to enterprise-knowledge/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without uploading anything.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload every document even when the content hash and metadata match.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every document, including unchanged ones.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Values come from the real environment when present, otherwise from .env.
    load_dotenv(REPO_ROOT / ".env")

    args = build_parser().parse_args(argv)

    if not args.account_name:
        print(
            "error: storage account name is required. Pass --account-name or set "
            "AZURE_STORAGE_ACCOUNT_NAME (for example in .env).",
            file=sys.stderr,
        )
        return EXIT_CONFIGURATION_ERROR

    try:
        result = sync(
            source=Path(args.source).resolve(),
            container=args.container,
            account_name=args.account_name,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    print_report(
        result,
        container=args.container,
        account=args.account_name,
        dry_run=args.dry_run,
    )

    return EXIT_PARTIAL_FAILURE if result.failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
