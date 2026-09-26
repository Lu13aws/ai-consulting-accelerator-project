#!/usr/bin/env python3
"""
Ingest the personal-toolkit Skills into the shared pgvector store under app_name="skills".

This is the first source of the platform's "Organizational Memory": the Consulting
Accelerator can then retrieve relevant *existing* internal knowledge (with sources) during
an engagement — grounded references, never invented claims. Skills are internal,
non-confidential knowledge, so they live in the shared store (NOT the isolated engagement DB).

Reuses the proven aiplatform pipeline (load -> dedup -> chunk -> embed -> store), exactly like
scripts/ingest_frameworks.py, with two differences:
  * walks <skills>/**/SKILL.md (Markdown — handled by aiplatform's MarkdownLoader)
  * source_uri = skill://<category>/<name>;  doc_metadata = {category, name, knowledge_type}

Usage:
    uv run python scripts/ingest_skills.py --dry-run
    uv run python scripts/ingest_skills.py                       # default toolkit skills dir
    uv run python scripts/ingest_skills.py --folder <path> --limit 12
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from aiplatform.ingestion.chunker import Chunker
from aiplatform.ingestion.deduplication import content_changed, hash_content
from aiplatform.ingestion.loaders import _strip_markdown
from aiplatform.llm import get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.storage.database import get_async_session
from aiplatform.storage.models import Chunk, Document, Embedding
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

APP_NAME = "skills"

# Default source: the sibling personal toolkit's skills/ tree (override with SKILLS_DIR).
DEFAULT_SKILLS_DIR = Path(
    os.environ.get(
        "SKILLS_DIR",
        Path(__file__).resolve().parents[2] / "personal-data-engineering-toolkit" / "skills",
    )
)


def derive_category_name(path: Path) -> tuple[str, str]:
    """skills/<category>/<name>/SKILL.md -> (category, name)."""
    name = path.parent.name
    category = path.parent.parent.name
    return category, name


# Frontmatter keys we recognise (capability metadata). `description` is the business-language
# bridge that gets PREPENDED to the embedded text; the rest are stored for later filtering.
_META_KEYS = ("description", "domains", "capabilities")


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a leading `---`…`---` YAML-ish block. Tiny parser (scalars + `[a, b]` lists) — no
    PyYAML dependency. Returns (metadata, body); ({}, raw) when there is no frontmatter."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, raw
    meta: dict = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
        elif val:
            meta[key] = val.strip("'\"")
    return meta, "\n".join(lines[end + 1 :])


def collect_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("SKILL.md"))


async def ingest_one(session, path: Path) -> tuple[str, int, str]:
    category, name = derive_category_name(path)
    source_uri = f"skill://{category}/{name}"

    raw = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(raw)
    content = _strip_markdown(body)
    if not content.strip():
        return ("failed", 0, "no extractable text")

    description = fm.get("description")
    # Identity hash covers description + body so re-tagging triggers a re-embed.
    new_hash = hash_content(f"{description}\n\n{content}" if description else content)
    existing_by_uri = await session.scalar(
        select(Document).where(Document.source_uri == source_uri)
    )
    if existing_by_uri is not None:
        if not content_changed(new_hash, existing_by_uri.content_hash):
            return ("skipped", 0, "unchanged")
        await session.execute(sql_delete(Document).where(Document.id == existing_by_uri.id))
        await session.flush()
    else:
        existing_by_hash = await session.scalar(
            select(Document).where(Document.content_hash == new_hash)
        )
        if existing_by_hash is not None:
            return ("skipped", 0, f"identical content already indexed ({existing_by_hash.source_uri})")

    metadata = {"filename": path.name, "category": category, "name": name, "knowledge_type": "skill"}
    metadata.update({k: fm[k] for k in _META_KEYS if k in fm})
    chunker = Chunker()
    chunks = chunker.split(content, metadata=metadata)
    if description:
        # Embed the business-language description as its OWN chunk — prepending it into a long
        # technical chunk dilutes the signal, so a business query still wouldn't match. As a
        # standalone chunk it is a pure business-language vector that bridges to the skill.
        chunks = chunker.split(description, metadata={**metadata, "part": "description"}) + chunks
    if not chunks:
        return ("failed", 0, "produced 0 chunks")

    embedder = Embedder(get_llm_provider())
    embedding_responses = await embedder.embed_chunks(chunks)

    doc_id = uuid4()
    session.add(
        Document(
            id=doc_id,
            source_uri=source_uri,
            content_hash=new_hash,
            title=name,
            mime_type="text/markdown",
            doc_metadata=metadata,
            app_name=APP_NAME,
        )
    )
    await session.flush()
    tag = " +desc" if description else ""

    chunk_ids: list = []
    for idx, chunk in enumerate(chunks):
        chunk_id = uuid4()
        chunk_ids.append(chunk_id)
        session.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=idx,
                content=chunk.content,
                content_hash=hash_content(chunk.content),
                token_count=chunk.token_count,
                chunk_metadata=chunk.metadata,
            )
        )
    await session.flush()

    for chunk_id, emb in zip(chunk_ids, embedding_responses, strict=True):
        session.add(
            Embedding(
                id=uuid4(),
                chunk_id=chunk_id,
                vector=emb.vector,
                model=emb.model,
                provider=emb.provider.value,
            )
        )
    return ("ingested", len(chunks), f"{len(chunks)} chunks{tag}")


async def run(files: list[Path], dry_run: bool) -> int:
    totals = {"ingested": 0, "skipped": 0, "failed": 0}
    total_chunks = 0
    print(f"\napp_name : {APP_NAME}\nFiles    : {len(files)} SKILL.md")
    print(f"Mode     : {'DRY-RUN' if dry_run else 'INGEST'}\n")

    if dry_run:
        for path in files:
            category, name = derive_category_name(path)
            print(f"  [would ingest] skill://{category}/{name}")
        print(f"\n{len(files)} file(s) would be processed.")
        return 0

    for idx, path in enumerate(files, start=1):
        category, name = derive_category_name(path)
        prefix = f"  [{idx}/{len(files)}] skill://{category}/{name}"
        try:
            async with get_async_session() as session:
                status, chunks_created, message = await ingest_one(session, path)
            totals[status] += 1
            total_chunks += chunks_created
            print(f"{prefix}\n        [{ {'ingested':'ok','skipped':'skip','failed':'err'}[status] }] {message}")
        except Exception as exc:  # noqa: BLE001
            totals["failed"] += 1
            print(f"{prefix}\n        [err] {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print(f"Done: {totals['ingested']} ingested | {totals['skipped']} skipped | "
          f"{totals['failed']} failed | {total_chunks} chunks")
    return 1 if totals["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest toolkit Skills into pgvector (app_name=skills).")
    parser.add_argument("--folder", type=str, help=f"Skills dir (default: {DEFAULT_SKILLS_DIR}).")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N files.")
    parser.add_argument("--dry-run", action="store_true", help="List only; no API calls or DB writes.")
    args = parser.parse_args()

    folder = Path(args.folder) if args.folder else DEFAULT_SKILLS_DIR
    if not folder.is_dir():
        print(f"Error: folder not found: {folder}")
        sys.exit(1)
    files = collect_files(folder)
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        print("No SKILL.md files found.")
        sys.exit(0)

    sys.exit(asyncio.run(run(files, args.dry_run)))


if __name__ == "__main__":
    main()
