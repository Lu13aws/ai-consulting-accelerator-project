#!/usr/bin/env python3
"""
Ingest Radar / Competitor / Regulatory reports from S3 into the LOCAL pgvector store.

Organizational Memory sources beyond the toolkit Skills. Reads the weekly report JSONs the
platform writes to S3, converts them with the platform's own converters, and indexes them
locally (one `app_name` per report type) so a consulting engagement can surface relevant
reports as cited references.

READS from S3 only; WRITES only to the local store (never the prod RDS). Reuses the proven
aiplatform load -> dedup -> chunk -> embed -> store pipeline (cf. ingest_skills.py).

Usage:
    uv run python scripts/ingest_reports_local.py --dry-run
    uv run python scripts/ingest_reports_local.py --type radar --latest
    uv run python scripts/ingest_reports_local.py                 # all types, all reports
"""

import argparse
import asyncio
import json
import sys
from uuid import uuid4

import boto3
from aiplatform.agents.report_indexer import _CONVERTERS, _fmt_date
from aiplatform.ingestion.chunker import Chunker
from aiplatform.ingestion.deduplication import content_changed, hash_content
from aiplatform.llm import get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.storage.database import get_async_session
from aiplatform.storage.models import Chunk, Document, Embedding
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

BUCKET = "ai-platform-documents-dev"
REGION = "eu-central-1"
# report_type -> S3 prefix. app_name == report_type (one app_name per type, cleanly filterable).
PREFIXES = {
    "radar": "radar/reports/",
    "competitor": "competitor/reports/",
    "regulatory": "regulatory/reports/",
}


def list_keys(s3, report_type: str, latest_only: bool) -> list[str]:
    prefix = PREFIXES[report_type]
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(".json") and "latest" not in k:
                keys.append(k)
    keys.sort()
    return keys[-1:] if (latest_only and keys) else keys


def source_uri(report_type: str, key: str) -> str:
    return f"{report_type}://" + key.removeprefix(PREFIXES[report_type]).removesuffix(".json")


async def ingest_one(session, s3, report_type: str, key: str) -> tuple[str, int, str]:
    label, converter = _CONVERTERS[report_type]
    report = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    content = converter(report)
    if not content.strip():
        return ("failed", 0, "empty report text")

    uri = source_uri(report_type, key)
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
        "category": report_type,
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
            title=f"{label} Report — {_fmt_date(report.get('generated_at', key))}",
            mime_type="application/json",
            doc_metadata=metadata,
            app_name=report_type,
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


async def run(s3, jobs: list[tuple[str, str]], dry_run: bool) -> int:
    print(f"\nbucket : {BUCKET}\nreports: {len(jobs)} (app_name = report type)")
    print(f"mode   : {'DRY-RUN' if dry_run else 'INGEST (S3 read, local write)'}\n")
    if dry_run:
        for rtype, key in jobs:
            print(f"  [would ingest] {source_uri(rtype, key)}")
        return 0
    totals = {"ingested": 0, "skipped": 0, "failed": 0}
    total_chunks = 0
    for i, (rtype, key) in enumerate(jobs, 1):
        try:
            async with get_async_session() as session:
                status, n, msg = await ingest_one(session, s3, rtype, key)
            totals[status] += 1
            total_chunks += n
            print(f"  [{i}/{len(jobs)}] {source_uri(rtype, key)}\n        [{ {'ingested':'ok','skipped':'skip','failed':'err'}[status] }] {msg}")
        except Exception as exc:  # noqa: BLE001
            totals["failed"] += 1
            print(f"  [{i}/{len(jobs)}] {source_uri(rtype, key)}\n        [err] {type(exc).__name__}: {exc}")
    print("\n" + "=" * 60)
    print(f"Done: {totals['ingested']} ingested | {totals['skipped']} skipped | "
          f"{totals['failed']} failed | {total_chunks} chunks")
    return 1 if totals["failed"] else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest S3 radar/competitor/regulatory reports into local pgvector.")
    ap.add_argument("--type", choices=[*PREFIXES, "all"], default="all", help="Report type (default: all).")
    ap.add_argument("--latest", action="store_true", help="Only the newest report per type.")
    ap.add_argument("--limit", type=int, default=None, help="Process only the first N reports per type.")
    ap.add_argument("--dry-run", action="store_true", help="List only; no S3 download / DB writes.")
    args = ap.parse_args()

    types = list(PREFIXES) if args.type == "all" else [args.type]
    s3 = boto3.client("s3", region_name=REGION)
    jobs: list[tuple[str, str]] = []
    for rtype in types:
        keys = list_keys(s3, rtype, args.latest)
        if args.limit is not None:
            keys = keys[: args.limit]
        jobs.extend((rtype, k) for k in keys)
    if not jobs:
        print("No reports found.")
        sys.exit(0)
    sys.exit(asyncio.run(run(s3, jobs, args.dry_run)))


if __name__ == "__main__":
    main()
