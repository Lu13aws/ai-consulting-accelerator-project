#!/usr/bin/env python3
"""
Ingest project README files into the LOCAL pgvector store (app_name="projects").

The fifth Organizational Memory source: "project knowledge" — a README captures how a project
was built and (in its Architecture / Lessons / Decisions sections) why. So a consulting
engagement can surface a resembling prior project as a cited reference to validate.

READMEs are long and multi-topic, which embeds diffusely — so (like skills) we LLM-seed a ONE
LINE business-language `description` per project and embed it as its OWN chunk, bridging a
business problem to the technically-worded README. Internal, non-confidential projects only.

Reads files only; writes the LOCAL store only. Reuses the aiplatform load -> chunk -> embed ->
store pipeline (cf. ingest_skills.py).

Usage:
    uv run python scripts/ingest_projects_local.py --dry-run
    uv run python scripts/ingest_projects_local.py
"""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from aiplatform.ingestion.chunker import Chunker
from aiplatform.ingestion.deduplication import content_changed, hash_content
from aiplatform.ingestion.loaders import _strip_markdown
from aiplatform.llm import Message, get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.storage.database import get_async_session
from aiplatform.storage.models import Chunk, Document, Embedding
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

APP_NAME = "projects"

# (path, slug, label) — slugs are the user's friendly project names (clean, human-readable).
PROJECTS = [
    (r"C:\Users\lucia\airbnb-project", "airbnb", "Airbnb Project"),
    (r"C:\Users\lucia\health_project", "health", "Health Project"),
    (r"C:\Users\lucia\git_projects\ai-consulting-accelerator-project", "ai-consulting", "AI Consulting Project"),
    (r"C:\Users\lucia\git_projects\ai-platform-project-v1", "ai-platform", "AI Platform Project"),
    (r"C:\Users\lucia\git_projects\aws-data-engineering-project", "energy", "Energy Project"),
    (r"C:\Users\lucia\git_projects\aws-real-time-analytics-project", "maritime", "Maritime Project"),
    (r"C:\Users\lucia\git_projects\myporfolio-website-project", "website", "Portfolio Website"),
]

_DESC_SYSTEM = """\
Write ONE business-language sentence describing what this project IS and the business problem it
addresses — plain terms a non-technical client would recognise, so a customer problem can be matched
to it. 12-24 words. Start with a noun/verb phrase (no "This project"). Output ONLY the sentence."""


def find_readme(path: Path) -> Path | None:
    for cand in ("README.md", "Readme.md", "readme.md"):
        if (path / cand).is_file():
            return path / cand
    hits = sorted(path.glob("README*"))
    return hits[0] if hits else None


async def describe(provider, label: str, body: str) -> str:
    resp = await provider.complete(
        [Message(role="user", content=f"Project: {label}\n\nREADME:\n{body[:3000]}")],
        system_prompt=_DESC_SYSTEM,
        temperature=0,
        max_tokens=70,
    )
    return " ".join(resp.content.replace("\n", " ").split()).strip().strip('"').rstrip(".")


async def ingest_one(session, provider, readme: Path, slug: str, label: str) -> tuple[str, int, str]:
    content = _strip_markdown(readme.read_text(encoding="utf-8", errors="replace"))
    if not content.strip():
        return ("failed", 0, "empty README")

    # Identity = the README content only (the LLM `description` is derived and not perfectly
    # deterministic). Check dedup BEFORE generating the description, so an unchanged README
    # skips with no LLM call — the refresh is then truly idempotent.
    uri = f"project://{slug}"
    new_hash = hash_content(content)
    existing = await session.scalar(select(Document).where(Document.source_uri == uri))
    if existing is not None and not content_changed(new_hash, existing.content_hash):
        return ("skipped", 0, "unchanged")

    description = await describe(provider, label, content)
    if existing is not None:
        await session.execute(sql_delete(Document).where(Document.id == existing.id))
        await session.flush()

    metadata = {"slug": slug, "label": label, "knowledge_type": "project", "description": description}
    chunker = Chunker()
    chunks = chunker.split(description, metadata={**metadata, "part": "description"}) + chunker.split(
        content, metadata=metadata
    )

    embeddings = await Embedder(provider).embed_chunks(chunks)

    doc_id = uuid4()
    session.add(
        Document(
            id=doc_id,
            source_uri=uri,
            content_hash=new_hash,
            title=label,
            mime_type="text/markdown",
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
    return ("ingested", len(chunks), f"{len(chunks)} chunks | desc: {description}")


def resolve_jobs(from_dir: Path | None) -> list[tuple[Path, str, str]]:
    """(readme_path, slug, label) per project. Either the curated local PROJECTS list, or — for
    the in-VPC/prod ingest — every `<slug>.md` in a directory (label derived from the slug)."""
    if from_dir is not None:
        jobs = []
        for md in sorted(Path(from_dir).glob("*.md")):
            slug = md.stem
            jobs.append((md, slug, slug.replace("-", " ").replace("_", " ").title()))
        return jobs
    jobs = []
    for path, slug, label in PROJECTS:
        readme = find_readme(Path(path))
        if readme is not None:
            jobs.append((readme, slug, label))
    return jobs


async def run(dry_run: bool, from_dir: Path | None = None) -> int:
    jobs = resolve_jobs(from_dir)
    print(f"\napp_name : {APP_NAME}\nprojects : {len(jobs)}{' (from ' + str(from_dir) + ')' if from_dir else ''}")
    print(f"mode     : {'DRY-RUN' if dry_run else 'INGEST (read files, local write)'}\n")
    if dry_run:
        for readme, slug, _label in jobs:
            print(f"  project://{slug:14} <- {readme}")
        return 0

    provider = get_llm_provider()
    totals = {"ingested": 0, "skipped": 0, "failed": 0}
    total_chunks = 0
    for i, (readme, slug, label) in enumerate(jobs, 1):
        try:
            async with get_async_session() as session:
                status, n, msg = await ingest_one(session, provider, readme, slug, label)
            totals[status] += 1
            total_chunks += n
            print(f"  [{i}/{len(jobs)}] project://{slug}\n        [{ {'ingested':'ok','skipped':'skip','failed':'err'}[status] }] {msg}")
        except Exception as exc:  # noqa: BLE001
            totals["failed"] += 1
            print(f"  [{i}/{len(jobs)}] project://{slug}\n        [err] {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print(f"Done: {totals['ingested']} ingested | {totals['skipped']} skipped | "
          f"{totals['failed']} failed | {total_chunks} chunks")
    return 1 if totals["failed"] else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest project READMEs into local pgvector (app_name=projects).")
    ap.add_argument("--from-dir", type=str, help="Ingest every <slug>.md in this directory (prod/in-VPC mode).")
    ap.add_argument("--dry-run", action="store_true", help="List planned project:// URIs; no LLM/DB writes.")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.dry_run, Path(args.from_dir) if args.from_dir else None)))


if __name__ == "__main__":
    main()
