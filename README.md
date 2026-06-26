# AI Consulting Accelerator

AI-assisted consulting workflow built on a retrieval-augmented knowledge base of
industry frameworks. The system ingests BA/RE/PM standards (IREB, BABOK, BPMN, PMBOK,
Scrum, roadmapping) into a pgvector store, answers framework questions with citations,
and turns unstructured customer input into structured, framework-grounded consulting
drafts across a Discovery → Analysis → Delivery workflow.

> Every output is an **AI-generated draft for human review**, grounded in cited
> frameworks. See [CLAUDE.md](CLAUDE.md) for scope, principles and roadmap, and
> [DEPLOY.md](DEPLOY.md) for the deployment runbook.

---

## Project Structure

```
ai-consulting-accelerator-project/
├── apps/
│   ├── consulting_api/             # FastAPI backend
│   │   ├── main.py                 # app, CORS, idempotent schema bootstrap
│   │   ├── lambda_handler.py       # Mangum adapter + one-off {"action":"ingest"}
│   │   ├── api/
│   │   │   ├── routes.py           # generic /api/v1 routes (query, structure, skills, sources)
│   │   │   ├── consulting_routes.py# UI-facing /api/v1/consulting/* alias routes
│   │   │   └── schemas.py          # Pydantic request/response models
│   │   └── services/
│   │       ├── consulting_service.py  # query() + structure_artifact() (RAG, language lock)
│   │       └── skills.py           # named/versioned structuring skill registry (by layer)
│   └── consulting_ui/              # Next.js demo UI (sidebar app, dark theme, static export)
│       └── src/{app,components,lib}
├── scripts/
│   ├── ingest_frameworks.py        # bulk .pdf/.html ingestion (dedup, language/category metadata)
│   ├── deploy.py                   # Lambda container + API Gateway HTTP API (VPC, JWT)
│   ├── deploy_frontend.py          # build + ship UI to S3 + CloudFront
│   └── setup_consulting_cognito.py # (optional) Cognito demo pool
├── data/                           # framework PDFs, grouped by category
├── tests/                          # pytest: skills, ingestion helpers, API
├── infra/                          # vpc_config.json (gitignored; copied from the platform repo)
├── CLAUDE.md  DEPLOY.md  README.md
└── pyproject.toml                  # aiplatform installed editable via [tool.uv.sources]
```

---

## Architecture

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Mangum (Python 3.12, `uv`) |
| Vector store | PostgreSQL + pgvector — local Docker for dev; shared `ai-platform-db-v2` (VPC-private) in prod |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| LLM | OpenAI `gpt-4o-mini` (provider swappable via `aiplatform`) |
| Frontend | Next.js (App Router, TypeScript, Tailwind v4, lucide-react), static export |
| Reused platform code | `aiplatform`: loaders, chunker, embedder, vector store, LLM providers, ORM models, settings |
| Deployment (scripts ready, not yet run) | Lambda container + API Gateway HTTP API (in VPC); S3 + CloudFront for the UI |

Documents from all apps share one schema (`documents` / `chunks` / `embeddings`); this
product scopes everything with `app_name="consulting"`.

---

## Final Data Flow

**Ingestion (one-time / on framework updates):**

```
data/*.pdf  (and *.html)
→ scripts/ingest_frameworks.py        (recursive walk, SHA-256 dedup)
→ aiplatform PDF / HTML loader
→ Chunker                              (800-token chunks)
→ OpenAI text-embedding-3-small
→ pgvector: documents / chunks / embeddings   (app_name="consulting")
```

**Framework Q&A (RAG):**

```
User question  (UI /chat)
→ POST /api/v1/consulting/query
→ embed question (OpenAI)
→ pgvector cosine search               (scoped to app_name="consulting")
→ grounded prompt + retrieved chunks
→ LLM (gpt-4o-mini)
→ cited answer + source panel
```

**Structuring & Discovery skills:**

```
User input  (UI /structure, /discovery, /stakeholders)
→ POST /api/v1/consulting/{structure/*, run, stakeholders}
→ named skill (skills registry) + server-side language detect (DE/EN lock)
→ retrieve grounding chunks            (filtered to the input language)
→ LLM → structured Markdown artifact + sources + draft disclaimer
```

---

## Capabilities

The product is organised as a **Discovery → Analysis → Delivery** workflow. Each
capability is a named, versioned **skill** (single-shot, grounded, cited, language-faithful).

| Layer | Tool | Endpoint |
|---|---|---|
| — | Framework Q&A (RAG) | `POST /api/v1/consulting/query` |
| Discovery | Business Problem structurer | `POST /api/v1/consulting/structure/problem` |
| Discovery | Stakeholder analysis (RACI, influence/interest, comms) | `POST /api/v1/consulting/stakeholders` |
| Discovery | Risks · Assumptions · Open Questions · Hypotheses · Interview Guide | `POST /api/v1/consulting/run` (`{skill, inputs}`) |
| Analysis | Requirements (classification + INVEST stories + quality flags) | `POST /api/v1/consulting/structure/requirements` |
| Delivery | Roadmap + agile backlog | `POST /api/v1/consulting/structure/roadmap` |
| — | List skills (with layer) | `GET /api/v1/consulting/skills` |

UI routes: `/dashboard` (tools grouped by layer), `/chat`, `/discovery`, `/structure`
(Business Problem / Requirements / Roadmap tabs), `/stakeholders`.

---

## Environment Setup

**Prerequisites:** Python 3.12, [`uv`](https://docs.astral.sh/uv/), Docker (local DB),
Node.js 20+ (UI), an OpenAI API key.

**1. Install dependencies** (resolves the editable `aiplatform` sibling dependency):

```bash
uv sync
```

**2. Local database.** `ai-platform-db-v2` is VPC-private and **not reachable from a
laptop** — use a local Docker pgvector for development:

```bash
# in the sibling platform repo (image: pgvector/pgvector:pg16, exposes localhost:5432)
cd ../ai-platform-project-v1 && docker compose up -d postgres
```

> The `documents` / `chunks` / `embeddings` tables are created automatically on first API
> startup (`main.py` runs an idempotent `Base.metadata.create_all`). The Docker volume
> persists data between runs.

**3. Configure `.env`** (copy `.env.example`, fill values — names only here):

```
APP_ENV, DATABASE_URL (postgresql+asyncpg://…), ALEMBIC_DATABASE_URL,
LLM_PROVIDER, OPENAI_API_KEY, OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL,
MAX_CHUNKS_PER_DOC
```

UI env (`apps/consulting_ui/.env.local`): `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`).

**4. Run:**

```bash
# API
uv run uvicorn apps.consulting_api.main:app --port 8000          # http://localhost:8000/docs

# UI (separate terminal)
cd apps/consulting_ui && npm install && npm run dev               # http://localhost:3000

# tests / lint
uv run pytest -q
uv run ruff check apps/ scripts/ tests/
```

---

## Framework Ingestion

Ingests `.pdf` and `.html`/`.htm` files from `data/` into pgvector. SHA-256 dedup means
unchanged files are skipped and never re-embedded.

```bash
uv run python scripts/ingest_frameworks.py --dry-run             # preview only, no API/DB
uv run python scripts/ingest_frameworks.py --folder data/        # bulk
uv run python scripts/ingest_frameworks.py --file <path.pdf>     # single file / re-ingest
uv run python scripts/ingest_frameworks.py --limit 1             # cost control while testing
```

Each document is stored with `source_uri = framework://<category>/<stem>`,
`app_name="consulting"`, and `doc_metadata = {category, language, filename}`.
Full bulk ingest of the framework set costs roughly **$2–5** in embeddings (one time).

> Saved web pages (e.g. SAFe) only ingest if a complete `.html` file exists; asset-only
> `*_files/` folders are skipped.

---

## Data Source

Industry frameworks stored as PDFs under `data/`, grouped by category:

- **Requirements Engineering** — IREB CPRE Foundation/Advanced (DE/EN), Requirements
  Management, UML, RE management overview
- **Business Analysis** — BABOK v3, Nutzwertanalyse
- **Process Management** — BPMN handbook + conventions
- **Project Management** — HBR PM guide, Scrum, Fraunhofer roadmapping study, backlog refs
- **Governance** — EU AI Act, GDPR, NIST CSF / SP 800-61r2 / IR 8596, AWS Well-Architected

Frameworks are permanent reference material — re-ingest only when a new version of a
standard is published.

---

## Challenges & Fixes

### Shared RDS unreachable from local dev

**Symptom:** `getaddrinfo failed` when the ingestion/API tried to reach `ai-platform-db-v2`.

**Root cause:** the RDS instance is `PubliclyAccessible: false` (private VPC subnets) — its
endpoint has no public DNS record. The CLAUDE.md label "public RDS" was inaccurate.

**Fix:** local development uses a Docker pgvector container; production ingestion runs from
**inside the VPC** (a one-off Lambda `{"action":"ingest"}` after deploy).

### Cross-lingual output drift in structuring skills

**Symptom:** German input sometimes produced English output (and one English input produced
Spanish headings) in the structuring/discovery skills.

**Root cause:** the model was left to self-detect language; German grounding chunks and
English template category lists in the prompt biased the output to the wrong language.

**Fix:** detect the input language server-side (`de`/`en`), pass an explicit
`"Write the entire response in <language>."` instruction, **and** filter retrieved grounding
chunks to the input language (by detected chunk-content language, since stored metadata is
often `unknown`).

### UI rendered white with faint text

**Symptom:** after a theme change the app showed a white background with barely-readable text.

**Root cause:** a stale dev server / `.next` cache kept serving old CSS, and the original
theme depended on the browser `prefers-color-scheme`.

**Fix:** force dark via explicit classes (not media-query dependent), clear `.next`, restart
the dev server, hard-refresh the browser.

### Lambda image must bundle a sibling-repo dependency

**Symptom:** `aiplatform` is an editable local path dependency — not present in the Docker
build context.

**Root cause:** the consulting repo consumes `aiplatform` from `../ai-platform-project-v1`.

**Fix:** `scripts/deploy.py` stages a build context that copies the `aiplatform` source plus a
generated `requirements.lambda.txt` (third-party deps only); the Dockerfile pip-installs the
third-party deps and copies `aiplatform` onto the Lambda task root (mirrors the platform's
own Lambda build).

### Large PDFs exceeded the per-document chunk cap

**Symptom:** three large PDFs failed ingestion (`exceeding the limit of 500`).

**Root cause:** `MAX_CHUNKS_PER_DOC=500` (an aiplatform cost-control cap).

**Fix:** raised to `1000` via `.env` (covers the largest framework PDFs).

---

## Lessons Learned

- A "public" shared RDS in a private VPC is unreachable from a laptop — verify
  `PubliclyAccessible` before assuming local access; keep a local Docker DB for dev.
- LLM output language is fragile: never rely on the model to infer it — detect it
  deterministically and instruct it explicitly; cross-language grounding context will flip
  the output otherwise.
- Browser/`.next` CSS caching masks theme changes — when "it still looks wrong", restart the
  dev server and hard-refresh before debugging the code.
- Most "agents" in a consulting product are really **skills** (single-shot structured output)
  — a named/versioned registry beats premature multi-agent infrastructure.
- Bump a skill's version whenever its prompt changes; treat prompts as versioned contracts.
- Store stored-document language at ingestion is unreliable from filenames — detect from
  content when it matters.

---

## Future Improvements

### Workflow depth (Phase 2)
- **Interview / Discovery mode** — multi-turn, stateful: analysis → hypotheses →
  clarification questions → refined analysis → requirements
- **Engagement persistence** on an **isolated DB** (confidential client data must never use
  the shared public `db-v2`)

### Delivery layer (Phase 3, high-caution)
- Architecture recommendation (grounded in AWS Well-Architected), effort/cost estimation and
  proposal generation — only with explicit confidence levels and "requires validation"

### Quality & ops
- Evaluation harness for output quality (language fidelity, grounding, structure)
- Auth for any client-facing / confidential use (Cognito JWT scaffolding already exists)
- Deploy the public demo (Lambda + API Gateway + S3/CloudFront) and a custom domain
- Content-based language tagging at ingestion (replace the filename heuristic)

---

## Project Progress

### 20260625

- Project scaffold: `pyproject.toml` wiring `aiplatform` as an editable `uv` source; structure, `.env`, `.gitignore`.
- Framework ingestion pipeline (`scripts/ingest_frameworks.py`); ingested the framework set (~5,380 chunks) into local pgvector.
- Consulting API: Framework Q&A (RAG + citations) and the first structuring skills (business problem, requirements, stakeholders, roadmap).
- pytest suite; Next.js demo UI (Q&A + structuring) with Cognito-gated auth.
- Deployment artifacts: `lambda_handler`, `Dockerfile.lambda`, `deploy.py`, `deploy_frontend.py`, `DEPLOY.md`; image build validated locally via the Lambda RIE.

### 20260626

**Rebuild UI as a platform-style app**
- Replaced the single-page UI with a dark sidebar app (Next.js, Tailwind, lucide-react) matching `platform.bridging-data.com`; removed auth for the public Phase-1 demo.

**Phase 1.5 — Discovery & Analysis depth**

**Observation**
The MVP behaved as a one-shot structuring tool; testing surfaced the need to investigate,
challenge assumptions and drive discovery.

**Solution**
Added a `layer` taxonomy (discovery/analysis/delivery); enriched the existing skills
(business-problem v1.3, requirements v1.3 with classification, stakeholders v1.2); added five
discovery skills (risks, assumptions, open-questions, hypotheses, interview-guide); a generic
`/api/v1/consulting/run` route; a Discovery UI page; locked output language server-side.

**Result**
Nine skills across three layers; 38 tests green; cross-lingual output drift fixed.

---

## Scripts

| Script | Purpose | Usage |
|---|---|---|
| `scripts/ingest_frameworks.py` | Ingest `data/` PDFs/HTML into pgvector (dedup, metadata) | `uv run python scripts/ingest_frameworks.py --folder data/` |
| `scripts/deploy.py` | Build/push Lambda image; provision Lambda + API Gateway (VPC, JWT). `--build-only` validates the image with no AWS | `uv run python scripts/deploy.py` |
| `scripts/deploy_frontend.py` | Build the static UI and ship to S3 + CloudFront | `uv run python scripts/deploy_frontend.py` |
| `scripts/setup_consulting_cognito.py` | (Optional) create the Cognito demo pool | `uv run python scripts/setup_consulting_cognito.py` |

> **Warnings:** `deploy.py` / `deploy_frontend.py` create real, billable AWS resources and
> require Docker + an authenticated AWS CLI + `infra/vpc_config.json`. `ingest_frameworks.py`
> makes OpenAI embedding calls (cost). See [DEPLOY.md](DEPLOY.md) for the full sequence.
