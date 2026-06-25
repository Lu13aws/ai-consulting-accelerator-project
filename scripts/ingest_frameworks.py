#!/usr/bin/env python3
"""
Bulk-ingest consulting framework documents into the shared pgvector DB.

Walks data/ recursively, picks up .pdf / .html / .htm files, and runs the proven
load -> dedup -> chunk -> embed -> store pipeline from aiplatform, scoping every
document with app_name="consulting".

This mirrors apps/rag_demo/services/ingest_service.py from ai-platform-project-v1
but with two consulting-specific traits:
  * documents are loaded from their real filesystem path, yet stored under a
    canonical source_uri of  framework://<category>/<filename-stem>
  * doc_metadata carries {category, language, filename}

SHA-256 dedup (Document.content_hash is unique) ensures unchanged files are never
re-embedded.

Usage:
    uv run python scripts/ingest_frameworks.py                 # bulk: all of data/
    uv run python scripts/ingest_frameworks.py --folder data/
    uv run python scripts/ingest_frameworks.py --file data/requirements_engineering/ireb_elicitation_summary.pdf
    uv run python scripts/ingest_frameworks.py --limit 1       # first N files only
    uv run python scripts/ingest_frameworks.py --dry-run       # list only, no API/DB
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path
from uuid import uuid4

from aiplatform.ingestion.chunker import Chunker
from aiplatform.ingestion.deduplication import content_changed, hash_content
from aiplatform.ingestion.loaders import get_loader
from aiplatform.llm import get_llm_provider
from aiplatform.retrieval.embedder import Embedder
from aiplatform.storage.database import get_async_session
from aiplatform.storage.models import Chunk, Document, Embedding
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

APP_NAME = "consulting"

# Only these are ingested. PDFs are the framework handbooks; HTML covers saved
# web pages (e.g. SAFe) once a complete .html file is present. Everything else
# (png/pptx/docx/css/js and Chrome "*_files" asset dirs) is skipped.
INGEST_EXTENSIONS = frozenset({".pdf", ".html", ".htm"})

DATA_ROOT_NAME = "data"


def derive_language(filename: str) -> str:
    """Best-effort language detection from filename tokens (_de_, -en-, ...)."""
    name = filename.lower()
    if re.search(r"[_\-]de[_\-.]", name):
        return "de"
    if re.search(r"[_\-]en[_\-.]", name):
        return "en"
    return "unknown"


def derive_category(path: Path, data_root: Path) -> str:
    """Top-level folder under data/ is the category; files directly in data/ -> 'general'."""
    try:
        rel = path.relative_to(data_root)
    except ValueError:
        return "general"
    parts = rel.parts
    return parts[0] if len(parts) > 1 else "general"


def derive_source_uri(category: str, path: Path) -> str:
    return f"framework://{category}/{path.stem}"


def find_data_root(start: Path) -> Path:
    """Resolve the data/ root regardless of where the chosen path sits."""
    for candidate in [start, *start.parents]:
        if candidate.name == DATA_ROOT_NAME:
            return candidate
    # --file given: walk up until we hit a 'data' ancestor, else use project data/
    for parent in start.parents:
        if (parent / DATA_ROOT_NAME).is_dir():
            return parent / DATA_ROOT_NAME
    return Path(__file__).resolve().parent.parent / DATA_ROOT_NAME


def collect_files(folder: Path) -> list[Path]:
    files = [
        p
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix.lower() in INGEST_EXTENSIONS
    ]
    return files


async def ingest_one(session, path: Path, data_root: Path) -> tuple[str, int, str]:
    """
    Returns (status, chunks_created, message).
    status in {"ingested", "skipped", "failed"}.
    """
    category = derive_category(path, data_root)
    language = derive_language(path.name)
    source_uri = derive_source_uri(category, path)

    # 1. Load from the real filesystem path
    loader = get_loader(str(path))
    loaded = await loader.load(str(path))

    if not loaded.content.strip():
        return ("failed", 0, "no extractable text (scanned image without OCR?)")

    # 2. Deduplication
    new_hash = hash_content(loaded.content)

    existing_by_uri = await session.scalar(
        select(Document).where(Document.source_uri == source_uri)
    )
    if existing_by_uri is not None:
        if not content_changed(new_hash, existing_by_uri.content_hash):
            return ("skipped", 0, "unchanged (same source_uri + hash)")
        # Changed: drop old document; cascade removes its chunks + embeddings
        await session.execute(sql_delete(Document).where(Document.id == existing_by_uri.id))
        await session.flush()
    else:
        existing_by_hash = await session.scalar(
            select(Document).where(Document.content_hash == new_hash)
        )
        if existing_by_hash is not None:
            return ("skipped", 0, f"identical content already indexed ({existing_by_hash.source_uri})")

    # 3. Chunk
    merged_metadata = {
        **loaded.metadata,
        "category": category,
        "language": language,
        "filename": path.name,
    }
    chunker = Chunker()
    chunks = chunker.split(loaded.content, metadata=merged_metadata)
    if not chunks:
        return ("failed", 0, "produced 0 chunks")

    # 4. Embed (single batch call)
    provider = get_llm_provider()
    embedder = Embedder(provider)
    embedding_responses = await embedder.embed_chunks(chunks)

    # 5. Persist: Document -> flush -> Chunks -> flush -> Embeddings
    doc_id = uuid4()
    session.add(
        Document(
            id=doc_id,
            source_uri=source_uri,
            content_hash=new_hash,
            title=loaded.metadata.get("filename", path.name),
            mime_type=loaded.mime_type,
            doc_metadata=merged_metadata,
            app_name=APP_NAME,
        )
    )
    await session.flush()

    chunk_ids: list = []
    for chunk in chunks:
        chunk_id = uuid4()
        chunk_ids.append(chunk_id)
        session.add(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=chunk.chunk_index,
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

    return ("ingested", len(chunks), f"{len(chunks)} chunks")


async def run(files: list[Path], data_root: Path, dry_run: bool) -> int:
    totals = {"ingested": 0, "skipped": 0, "failed": 0}
    total_chunks = 0

    print(f"\nData root : {data_root}")
    print(f"app_name  : {APP_NAME}")
    print(f"Files     : {len(files)} ({', '.join(sorted(INGEST_EXTENSIONS))})")
    print(f"Mode      : {'DRY-RUN (no API calls, no DB writes)' if dry_run else 'INGEST'}\n")

    if dry_run:
        for path in files:
            category = derive_category(path, data_root)
            print(f"  [would ingest] {derive_source_uri(category, path)}  <-  {path.name}")
        print(f"\n{len(files)} file(s) would be processed.")
        return 0

    for idx, path in enumerate(files, start=1):
        prefix = f"  [{idx}/{len(files)}] {path.name}"
        try:
            # One transaction per file: a failure rolls back only that file.
            async with get_async_session() as session:
                status, chunks_created, message = await ingest_one(session, path, data_root)
            totals[status] += 1
            total_chunks += chunks_created
            tag = {"ingested": "ok", "skipped": "skip", "failed": "err"}[status]
            print(f"{prefix}\n        [{tag}] {message}")
        except Exception as exc:  # noqa: BLE001 — report and continue with next file
            totals["failed"] += 1
            print(f"{prefix}\n        [err] {type(exc).__name__}: {exc}")

    print("\n" + "=" * 60)
    print(
        f"Done: {totals['ingested']} ingested  |  {totals['skipped']} skipped  |  "
        f"{totals['failed']} failed  |  {total_chunks} chunks created"
    )
    return 1 if totals["failed"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest consulting frameworks into pgvector.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--folder", type=str, help="Folder to ingest recursively (default: data/).")
    group.add_argument("--file", type=str, help="Ingest a single file.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N files.")
    parser.add_argument("--dry-run", action="store_true", help="List only; no API calls or DB writes.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent

    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = (project_root / target).resolve()
        if not target.is_file():
            print(f"Error: file not found: {target}")
            sys.exit(1)
        if target.suffix.lower() not in INGEST_EXTENSIONS:
            print(f"Error: unsupported extension '{target.suffix}'. Allowed: {', '.join(sorted(INGEST_EXTENSIONS))}")
            sys.exit(1)
        data_root = find_data_root(target)
        files = [target]
    else:
        folder = Path(args.folder) if args.folder else (project_root / DATA_ROOT_NAME)
        if not folder.is_absolute():
            folder = (project_root / folder).resolve()
        if not folder.is_dir():
            print(f"Error: folder not found: {folder}")
            sys.exit(1)
        data_root = find_data_root(folder)
        files = collect_files(folder)

    if args.limit is not None:
        files = files[: args.limit]

    if not files:
        print("No ingestible files found.")
        sys.exit(0)

    exit_code = asyncio.run(run(files, data_root, args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
