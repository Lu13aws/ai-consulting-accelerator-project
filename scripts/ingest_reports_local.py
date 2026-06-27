#!/usr/bin/env python3
"""
Ingest Technology Radar reports from S3 into the LOCAL pgvector store (app_name="radar").

Organizational Memory, second source (pilot — radar only). Reads the weekly report JSONs the
platform writes to S3, converts them with the platform's own `radar_to_text`, and indexes them
locally so a consulting engagement can surface relevant radar reports as cited references.

READS from S3 only; WRITES only to the local store (never the prod RDS). Reuses the proven
aiplatform load -> dedup -> chunk -> embed -> store pipeline (cf. ingest_skills.py).

Usage:
    uv run python scripts/ingest_reports_local.py --dry-run
    uv run python scripts/ingest_reports_local.py --latest      # only the newest report
    uv run python scripts/ingest_reports_local.py               # all radar reports
"""

import argparse
import asyncio
import json
import sys
from uuid import uuid4

import boto3
from aiplatform.agents.report_indexer import _fmt_date, radar_to_text
from aiplatform.ingestion.chunker import Chunker
from aiplatform.ingestion.deduplication import content_changed, hash_content
from aiplatform.llm import get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.storage.database import get_async_session
from aiplatform.storage.models import Chunk, Document, Embedding
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

APP_NAME = "radar"
BUCKET = "ai-platform-documents-dev"
REGION = "eu-central-1"
PREFIX = "radar/reports/"


def list_keys(s3, latest_only: bool) -> list[str]:
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(".json") and "latest" not in k:
                keys.append(k)
    keys.sort()
    return keys[-1:] if (latest_only and keys) else keys


def source_uri(key: str) -> str:
    return "radar://" + key.removeprefix(PREFIX).removesuffix(".json")


async def ingest_one(session, s3, key: str) -> tuple[str, int, str]:
    report = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    content = radar_to_text(report)
    if not content.strip():
        return ("failed", 0, "empty report text")

    uri = source_uri(key)
    new_hash = hash_content(content)
    existing = await session.scalar(select(Document).where(Document.source_uri == uri))
    if existing is not None:
        if not content_changed(new_hash, existing.content_hash):
            return ("skipped", 0, "unchanged")
        await session.execute(sql_delete(Document).where(Document.id == existing.id))
        await session.flush()
    else:
        dup = await session.scalar(select(Document).where(Document.content_hash == new_hash))
        if dup is not None:
            return ("skipped", 0, f"identical content already indexed ({dup.source_uri})")

    metadata = {
        "category": "radar",
        "report_type": "technology",
        "knowledge_type": "report",
        "generated_at": report.get("generated_at"),
        "s3_key": key,
    }
    chunks = Chunker().split(content, metadata=metadata)
    if not chunks:
        return ("failed", 0, "produced 0 chunks")

    embeddings = await Embedder(get_llm_provider()).embed_chunks(chunks)

    doc_id = uuid4()
    session.add(
        Document(
            id=doc_id,
            source_uri=uri,
            content_hash=new_hash,
            title=f"Technology Radar Report — {_fmt_date(report.get('generated_at', key))}",
            mime_type="application/json",
            doc_metadata=metadata,
            app_name=APP_NAME,
        )
    )
    await session.flush()

    chunk_ids: list = []
    for idx, chunk in enumerate(chunks):
        cid = uuid4()
        chunk_ids.append(cid)
        session.add(
            Chunk(
                id=cid,
                document_id=doc_id,
                chunk_index=idx,
                content=chunk.content,
                content_hash=hash_content(chunk.content),
                token_count=chunk.token_count,
                chunk_metadata=chunk.metadata,
            )
        )
    await session.flush()
    for cid, emb in zip(chunk_ids, embeddings, strict=True):
        session.add(
            Embedding(id=uuid4(), chunk_id=cid, vector=emb.vector, model=emb.model, provider=emb.provider.value)
        )
    return ("ingested", len(chunks), f"{len(chunks)} chunks")


async def run(s3, keys: list[str], dry_run: bool) -> int:
    print(f"\napp_name : {APP_NAME}\nbucket   : {BUCKET}\nreports  : {len(keys)}")
    print(f"mode     : {'DRY-RUN' if dry_run else 'INGEST (S3 read, local write)'}\n")
    if dry_run:
        for k in keys:
            print(f"  [would ingest] {source_uri(k)}")
        return 0
    totals = {"ingested": 0, "skipped": 0, "failed": 0}
    total_chunks = 0
    for i, key in enumerate(keys, 1):
        try:
            async with get_async_session() as session:
                status, n, msg = await ingest_one(session, s3, key)
            totals[status] += 1
            total_chunks += n
            print(f"  [{i}/{len(keys)}] {source_uri(key)}\n        [{ {'ingested':'ok','skipped':'skip','failed':'err'}[status] }] {msg}")
        except Exception as exc:  # noqa: BLE001
            totals["failed"] += 1
            print(f"  [{i}/{len(keys)}] {source_uri(key)}\n        [err] {type(exc).__name__}: {exc}")
    print("\n" + "=" * 60)
    print(f"Done: {totals['ingested']} ingested | {totals['skipped']} skipped | "
          f"{totals['failed']} failed | {total_chunks} chunks")
    return 1 if totals["failed"] else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest S3 Technology Radar reports into local pgvector.")
    ap.add_argument("--latest", action="store_true", help="Only the newest report.")
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N reports.")
    ap.add_argument("--dry-run", action="store_true", help="List only; no S3 download / DB writes.")
    args = ap.parse_args()

    s3 = boto3.client("s3", region_name=REGION)
    keys = list_keys(s3, args.latest)
    if args.limit is not None:
        keys = keys[: args.limit]
    if not keys:
        print("No radar reports found.")
        sys.exit(0)
    sys.exit(asyncio.run(run(s3, keys, args.dry_run)))


if __name__ == "__main__":
    main()
