# AI Consulting Accelerator

AI-assisted consulting workflow built on a retrieval-augmented knowledge base of
industry frameworks. The system ingests BA/RE/PM standards (IREB, BABOK, BPMN, PMBOK,
Scrum, roadmapping) into a pgvector store, answers framework questions with citations,
and turns unstructured customer input into structured, framework-grounded consulting
drafts across a Discovery → Analysis → Delivery workflow. It also recognises resembling
project archetypes and connects an engagement to prior internal knowledge (skills, radar
reports) as cited references to validate — an Organizational Memory, not an autonomous advisor.

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
│   │   │   ├── engagement_routes.py# /api/v1/consulting/engagements* (create/answer/conclude/generate/report/lifecycle)
│   │   │   └── schemas.py          # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── consulting_service.py  # query(), structure_artifact(), retrieve_knowledge(), derive_search_keywords()
│   │   │   ├── skills.py           # named/versioned structuring skill registry (by layer)
│   │   │   ├── patterns.py         # curated project-archetype catalog loader (Pattern Library)
│   │   │   ├── engagement_service.py  # multi-round discovery + hand-off + Organizational Memory step
│   │   │   ├── report_render.py    # engagement report → Markdown / Word (python-docx) / PDF (fpdf2)
│   │   │   └── eval_checks.py      # pure rule-based quality checks + judge-reply parsing
│   │   └── storage/
│   │       ├── engagement_db.py    # dedicated engine (CONSULTING_ENGAGEMENT_DB_URL — isolated DB)
│   │       └── engagement_models.py# Engagement ORM (turns/extras JSONB, archived, assessment)
│   └── consulting_ui/              # Next.js demo UI (sidebar app, dark theme, static export)
│       └── src/{app,components,lib}   # incl. app/engagements (guided Discovery→Analysis→Delivery)
├── scripts/
│   ├── ingest_frameworks.py        # bulk .pdf/.html ingestion (dedup, language/category metadata)
│   ├── ingest_skills.py            # toolkit SKILL.md → store under app_name="skills" (Organizational Memory)
│   ├── ingest_reports_local.py     # S3 radar/competitor/regulatory reports → local store (app_name per type)
│   ├── eval.py                     # quality eval harness (golden cases + rule checks + opt-in LLM judge)
│   ├── deploy.py                   # Lambda container + API Gateway HTTP API (VPC, JWT)
│   ├── deploy_frontend.py          # build + ship UI to S3 + CloudFront
│   └── setup_consulting_cognito.py # (optional) Cognito demo pool
├── data/                           # framework PDFs (by category) + patterns/ (curated project archetypes)
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

Documents from all apps share one schema (`documents` / `chunks` / `embeddings`), scoped by
`app_name`. Framework Q&A uses `app_name="consulting"`; the **Organizational Memory** (below)
reuses the same store under additional, independently-ingested `app_name`s (`skills`, `radar`,
`competitor`, `regulatory`) — a cross-source index without any new infrastructure.

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

**Engagements (Phase 2 — stateful, multi-round discovery):**

```
Initial situation  (UI /engagements)
→ POST /engagements                    create: analysis + hypotheses + open questions
→ POST /engagements/{id}/answer        repeatable round: Updated Findings (delta) + next, deeper questions
                                       (append-only JSONB `turns`; status=in_discovery)
→ POST /engagements/{id}/conclude      synthesis: classified requirements + consultant assessment
                                       (status=concluded)
→ POST /engagements/{id}/generate      hand-off: Roadmap / Stakeholder Analysis from the engagement
                                       context, attached under JSONB `extras` (one case file)
→ GET  /engagements/{id}/report        export everything as one file (?format=md|docx|pdf)
→ PATCH / DELETE /engagements/{id}     lifecycle: rename, archive (hidden by default), delete

Persisted via a DEDICATED engine (CONSULTING_ENGAGEMENT_DB_URL) — an isolated DB in prod,
never the shared public db-v2 (confidential client data).
```

**Organizational Memory (cross-source references — "connect existing knowledge, never invent"):**

```
Sources → ingested into the shared store, one app_name each (internal, non-confidential only):
  scripts/ingest_skills.py          toolkit SKILL.md            → app_name="skills"
  scripts/ingest_reports_local.py   S3 weekly reports (read-only) → "radar" / "competitor" / "regulatory"

Engagement "knowledge" step (consulting.relevant-knowledge):
  business context
  → derive_search_keywords()             distil business → technical keyword bag (bridge the vocabulary gap)
  → retrieve_knowledge([skills, radar, competitor, regulatory], threshold 0.25)   per-source caps (4/1/1/1)
  → cited references to VALIDATE (skill:// , radar:// …) — never recommendations, "none found" if nothing fits
```

---

## Capabilities

The product is organised as a **Discovery → Analysis → Delivery** workflow. Each
capability is a named, versioned **skill** (single-shot, grounded, cited, language-faithful).

**13 skills** across three layers, invoked by name (not similarity):

| Layer | Tool | Endpoint |
|---|---|---|
| — | Framework Q&A (RAG) | `POST /api/v1/consulting/query` |
| Discovery | Business Problem structurer | `POST /api/v1/consulting/structure/problem` |
| Discovery | Stakeholder analysis (RACI, influence/interest, comms) | `POST /api/v1/consulting/stakeholders` |
| Discovery | Risks · Assumptions · Open Questions · Hypotheses · Interview Guide | `POST /api/v1/consulting/run` (`{skill, inputs}`) |
| Analysis | Requirements (classification + INVEST stories + quality flags) | `POST /api/v1/consulting/structure/requirements` |
| Analysis | Refine analysis (delta) · Consultant assessment (preliminary) | via engagements / `run` |
| Analysis | **Match patterns** (resembling project archetypes, to validate) · **Relevant knowledge** (cross-source references) | via engagements `generate` |
| Delivery | Roadmap + agile backlog | `POST /api/v1/consulting/structure/roadmap` |
| — | List skills (with layer) | `GET /api/v1/consulting/skills` |

**Engagements** tie the layers into one stateful case file: multi-round discovery →
conclude (synthesis) → generate downstream artifacts (Roadmap · Stakeholder Analysis ·
**Pattern Fit** · **Relevant Knowledge**) → export (`md`/`docx`/`pdf`) →
lifecycle (rename/archive/delete). See the Engagements + Organizational-Memory data-flow
blocks above; endpoints under `POST/GET/PATCH/DELETE /api/v1/consulting/engagements*`
(`generate` `tool` = roadmap | stakeholders | patterns | knowledge).

UI routes: `/dashboard` (tools grouped by layer), `/chat`, `/discovery`, `/structure`
(Business Problem / Requirements / Roadmap tabs), `/stakeholders`, `/engagements`.

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
MAX_CHUNKS_PER_DOC,
CONSULTING_ENGAGEMENT_DB_URL   # engagement persistence; isolated DB in prod, falls back to DATABASE_URL locally
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

# quality eval harness (runs the real skills — costs ~cents; see below)
uv run python scripts/eval.py --dry-run                 # list golden cases, no LLM calls
uv run python scripts/eval.py                            # rule-based checks
uv run python scripts/eval.py --judge --judge-model gpt-4o   # + LLM content judge (advisory)
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

## Quality Eval Harness

`scripts/eval.py` runs golden cases (DE + EN, 16 across the skills) through the **real**
skills and scores each output. It calls the LLM, so run it on demand (e.g. after a
prompt/version change), not in CI.

**Rule-based checks** (`eval_checks.py` — pure, unit-tested): non-empty · language lock
(output language == input language) · draft disclaimer · structure (headings/table/list) ·
required sections (EN — DE headings get translated) · preliminary-framing caveats
(bilingual; guards "AI assists, does not decide") · confidence ranking (hypotheses) ·
citation integrity (no `[n]` without a matching source).

**Opt-in `--judge`** adds an LLM-as-judge pass scoring **groundedness / relevance /
citation faithfulness** (1–5) — a soft, advisory signal (warns on <3, never gates the exit
code). Default judge = the configured model (~free); `--judge-model gpt-4o` is a stronger,
more critical judge (~$0.06/full run) for before/after comparisons. (The cheap judge is
lenient — it scored a draft groundedness 5 where gpt-4o scored it 2.)

---

## Organizational Memory & Pattern Library

Two features that surface *prior, internal* knowledge during an engagement — both grounded,
cited, framed as **references/hypotheses to validate**, never recommendations.

**Pattern Library** (`data/patterns/*.md`, skill `consulting.match-patterns`): a small, curated
set of project archetypes (Corporate Knowledge Hub, Enterprise Search, AI Document Processing) —
each with typical goals/stakeholders/risks/assumptions/**pitfalls**. On a concluded engagement it
names 0–2 *resembling* archetypes (with confidence) and lists commonly-observed items to validate.
Deliberately discovery-scoped (no architecture/tech) so it stays on the "assists, not prescribes"
side; surfaced late (after understanding) to avoid anchoring.

**Organizational Memory** (cross-source retrieval, skill `consulting.relevant-knowledge`): indexes
other internal sources into the same pgvector store under their own `app_name`, then retrieves the
relevant ones during an engagement as cited references:

- `scripts/ingest_skills.py` → toolkit `SKILL.md` under `app_name="skills"` (`skill://…`)
- `scripts/ingest_reports_local.py` → weekly reports read **read-only from S3**, ingested **locally**
  under `app_name` = `radar` / `competitor` / `regulatory` (`radar://…`) — never the prod RDS

**Closing the business↔technical vocabulary gap** (the key finding) uses two complementary, simple
signals — *no clever retrieval pipeline*:
1. **Capability metadata** — an optional one-line, business-language `description:` in a `SKILL.md`
   YAML frontmatter, embedded as its OWN chunk so a business query matches a technically-worded skill.
2. **Query-side keyword expansion** — `derive_search_keywords()` distils the long, diffuse business
   context into a focused technical keyword bag.

`retrieve_knowledge()` queries the sources **per-source with caps** (≈ skills 4, radar/competitor/
regulatory 1 each) so dense weekly reports don't crowd out the how-to skills; the 0.25 similarity
threshold gates irrelevant sources out (honest "no relevant prior knowledge found", no fabrication).

> **Confidentiality:** only internal, non-confidential knowledge enters the shared store. Client
> engagement data stays in the isolated engagement DB and is never mixed in. Adding a source later
> = one more `(app_name, cap)` entry; a knowledge graph is deferred until traversal queries demand it.

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

### Done since the MVP
- ✅ **Interview / Discovery mode (Phase 2)** — stateful, multi-round engagements (turns →
  conclude), context hand-off to Roadmap/Stakeholders, one-file report export (md/docx/pdf),
  lifecycle (rename/archive/delete), persisted via a dedicated engine.
- ✅ **Quality eval harness** — golden cases + rule checks + opt-in LLM-as-judge.
- ✅ **Pattern Library + Organizational Memory** — resembling-archetype matching, and cross-source
  references from skills + radar/competitor/regulatory (local; capability metadata + keyword bridge).

### Organizational Memory — next
- **Freshness/automation** of the report ingest (currently a manual `ingest_reports_local.py` run)
- A real **multi-`app_name` filter** in `VectorStore.search` (one query instead of N per source)
- **ADRs / project docs** as a further source (scattered across repos — needs a format/location decision)
- Capability `description` on more skills; a knowledge graph only if traversal queries demand it

### Delivery layer (Phase 3, high-caution)
- Architecture recommendation (grounded in AWS Well-Architected), effort/cost estimation and
  proposal generation — only with explicit confidence levels and "requires validation"

### Quality & ops
- **Deploy** the public demo (Lambda + API Gateway + S3/CloudFront) and a custom domain
- A **real isolated DB** for engagements in prod (the dedicated engine + env seam exist;
  it currently falls back to `DATABASE_URL` locally) + auth for confidential use
  (Cognito JWT scaffolding already exists)
- Expand the eval harness: more golden cases, an `engagement`-flow case (covers
  `refine-analysis`), and periodic `gpt-4o` judge baselines
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

**Phase 2 — Engagements (stateful discovery) + quality**
- Stateful engagements: kickoff → **multi-round** answer loop (append-only `turns`, each round
  = delta-aware Updated Findings + next, deeper open questions) → **conclude** (classified
  requirements + a preliminary consultant assessment). Persisted via a dedicated engine
  (`CONSULTING_ENGAGEMENT_DB_URL`) — isolated DB in prod, never the shared public `db-v2`.
- Added skills `refine-analysis` (delta) and `consultant-assessment` (preliminary); hardened
  prompts (hypotheses ranked by confidence, context-aware questions, goal/requirement/story split).
- **Context hand-off:** generate Roadmap / Stakeholder Analysis from an engagement's context,
  attached under JSONB `extras` — the engagement becomes one Discovery→Analysis→Delivery case file.
- **Report export:** `GET /engagements/{id}/report?format=md|docx|pdf` composes every artifact
  into one downloadable file (Word via python-docx, PDF via fpdf2 — both pure-Python/Lambda-safe).
- **Lifecycle:** rename / archive (hidden by default) / delete; fixed a CORS gap (PATCH/DELETE
  were blocked by the browser preflight).
- **Quality eval harness** (`scripts/eval.py`): 16 golden cases (DE/EN) × rule-based checks
  (language lock, disclaimer, structure, sections, preliminary-framing, confidence, citations)
  + opt-in LLM-as-judge (groundedness/relevance/citations; `--judge-model gpt-4o`).

**Result**
11 skills; the full Discovery → Analysis → Delivery workflow as a single engagement case file;
66 tests green; quality measurable on demand.

### 20260627

**Pattern Library + Organizational Memory**

**Observation**
Two senior-consultant behaviours were missing: recognising that a problem *resembles* prior project
types, and *connecting* it to existing internal knowledge — without inventing claims (no "experience
layer") and without anchoring early or prescribing solutions.

**Solution**
- **Pattern Library:** curated archetypes (`data/patterns/`) + `consulting.match-patterns` — 0–2
  resembling patterns to validate, discovery-scoped, surfaced late.
- **Organizational Memory:** `consulting.relevant-knowledge` + `retrieve_knowledge()` over additional
  `app_name`s. `ingest_skills.py` indexes all 66 toolkit skills; `ingest_reports_local.py` reads radar/
  competitor/regulatory reports read-only from S3 into the local store. Multi-`app_name` retrieval with
  per-source caps.
- **Vocabulary bridge (key finding):** business problems and technical skills embed in different
  regions, so retrieval gave false negatives. Fixed *deterministically* with capability metadata
  (one-line business `description:` frontmatter embedded as its own chunk) **plus** query-side
  `derive_search_keywords()` — complementary, no clever pipeline.

**Result**
13 skills; engagements now surface resembling patterns + cited references from skills and the three
radar sources (relevance-gated, "none found" when nothing fits); 70 tests green. All local —
deploy/freshness deferred.

---

## Scripts

| Script | Purpose | Usage |
|---|---|---|
| `scripts/ingest_frameworks.py` | Ingest `data/` PDFs/HTML into pgvector (dedup, metadata) | `uv run python scripts/ingest_frameworks.py --folder data/` |
| `scripts/ingest_skills.py` | Ingest toolkit `SKILL.md` (parses `description` frontmatter) → `app_name="skills"` | `uv run python scripts/ingest_skills.py` |
| `scripts/ingest_reports_local.py` | Read radar/competitor/regulatory reports from S3 (read-only) → local store, `app_name` per type | `uv run python scripts/ingest_reports_local.py [--type radar] [--latest]` |
| `scripts/eval.py` | Quality eval: golden cases → rule checks (+ opt-in LLM judge). Calls the real LLM (~cents) | `uv run python scripts/eval.py [--judge --judge-model gpt-4o]` |
| `scripts/deploy.py` | Build/push Lambda image; provision Lambda + API Gateway (VPC, JWT). `--build-only` validates the image with no AWS | `uv run python scripts/deploy.py` |
| `scripts/deploy_frontend.py` | Build the static UI and ship to S3 + CloudFront | `uv run python scripts/deploy_frontend.py` |
| `scripts/setup_consulting_cognito.py` | (Optional) create the Cognito demo pool | `uv run python scripts/setup_consulting_cognito.py` |

> **Warnings:** `deploy.py` / `deploy_frontend.py` create real, billable AWS resources and
> require Docker + an authenticated AWS CLI + `infra/vpc_config.json`. `ingest_frameworks.py`
> makes OpenAI embedding calls (cost). See [DEPLOY.md](DEPLOY.md) for the full sequence.
