# AI Consulting Accelerator

AI-assisted platform for Business Analysis, Requirements Engineering, Process &
Project Management. Frameworks (IREB, BABOK, BPMN, PMBOK, …) are ingested as a
knowledge base and used to ground every answer in cited sources.

See [CLAUDE.md](CLAUDE.md) for the full architecture, scope and roadmap.

## Setup

This project reuses the `aiplatform` package from the sibling repo
`../ai-platform-project-v1` (installed editable via `[tool.uv.sources]`).

```bash
# 1. Install (resolves aiplatform editable + transitive deps)
uv sync

# 2. Configure env — copy and fill in DB + OpenAI credentials
cp .env.example .env   # then edit
```

`DATABASE_URL` must use the async driver (`postgresql+asyncpg://…`) and points at
the **shared** `ai-platform-db-v2`. Documents are scoped with `app_name="consulting"`.

## Framework Ingestion

Ingests `.pdf` and `.html`/`.htm` files from `data/` into the shared pgvector DB.
SHA-256 dedup: unchanged files are skipped, never re-embedded.

```bash
# Preview what would be ingested / skipped (no API calls, no DB writes)
uv run python scripts/ingest_frameworks.py --dry-run

# Ingest a single file (e.g. a newly updated standard)
uv run python scripts/ingest_frameworks.py --file data/requirements_engineering/ireb_elicitation_summary.pdf

# Bulk-ingest everything under data/
uv run python scripts/ingest_frameworks.py --folder data/

# Limit to the first N files (cost control while testing)
uv run python scripts/ingest_frameworks.py --limit 1
```

Each document is stored with:
- `source_uri`: `framework://<category>/<filename-stem>`
- `app_name`: `consulting`
- `doc_metadata`: `{"category": <folder>, "language": <de|en|unknown>, "filename": <name>}`

> **Note:** Saved web pages (e.g. SAFe) only ingest if a complete `.html` file is
> present. Asset-only `*_files/` folders are skipped.
