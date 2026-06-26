# CLAUDE.md — AI Consulting Accelerator

## Project Overview

AI-assisted platform for Business Analysis, Requirements Engineering, Process Management,
and Project Management. The system ingests industry frameworks as a knowledge base and uses
them to help practitioners structure, validate, and accelerate consulting work.

**Core principle:** AI assists — it does not replace human judgment.
Every output is a draft for human review, grounded in cited frameworks.

**Live demo target:** consulting.bridging-data.com (Phase 1)

---

## What This Product Is

An AI-assisted consulting **workflow** (Discovery → Analysis → Delivery) that:

1. Answers questions grounded in industry frameworks (IREB, BABOK, BPMN, PMBOK, etc.)
2. **Discovery:** structures the business situation and actively surfaces gaps —
   problem definition, stakeholders, risks, assumptions, open questions, hypotheses,
   interview guides
3. **Analysis:** turns understanding into structured solution design — requirement
   classification, INVEST user stories, quality checks
4. **Delivery:** supports planning — roadmap + agile backlog (estimation/architecture/
   proposals are a deferred, heavily-caveated future phase)
5. Helps practitioners apply frameworks without memorising every standard; demonstrates
   to potential clients how AI accelerates consulting workflows

**Layers are a product taxonomy over named skills, not separate systems.** Each skill is
a single-shot, grounded, cited, language-faithful Markdown draft. Multi-turn stateful
"interview mode" is a planned Phase 2 capability (not yet built).

## What This Product Is NOT

- Not an autonomous requirements generator — no structured input = no useful output
- Not a replacement for a trained BA, RE, or PM practitioner
- Not a cost estimator without detailed project data
- Not a legal, financial, or compliance tool
- Not a decision-maker — it structures information, humans decide
- Not a consulting firm — outputs are drafts, not professional deliverables

---

## Target Audience

**Primary:** Potential clients and portfolio visitors who want to see AI applied to consulting work.

**Secondary:** BA/RE/PM practitioners who want to accelerate their own documentation and structuring work.

---

## Framework Knowledge Base

Frameworks are stored as PDFs in `data/` and ingested via the aiplatform ingestion pipeline.
Each document is indexed with `app_name="consulting"` for scoped retrieval.

### Requirements Engineering

| File | Content |
|---|---|
| `cpre_foundationlevel_handbook_en_v1.3.0.pdf` | IREB CPRE Foundation Level (EN) |
| `cpre_foundationlevel_handbook_de_v1.3.2.pdf` | IREB CPRE Foundation Level (DE) |
| `advanced_level_elicitation_handbook_en_v2.2.0.pdf` | IREB Advanced Level — Elicitation (EN) |
| `advanced_level_elicitation_handbook_de_v2.2.1.pdf` | IREB Advanced Level — Elicitation (DE) |
| `ireb-cpre-handbook-for-requirements-management-en-v2.1.pdf` | IREB Requirements Management (EN) |
| `ireb-cpre-handbook-for-requirements-management-de-v2.1.pdf` | IREB Requirements Management (DE) |
| `ireb_cpre_handbook_requirements-modeling_advanced_level_en_v2.2.pdf` | IREB Requirements Modelling Advanced (EN) |
| `ireb_cpre_handbuch_requirements_modeling_advanced_level_de_v2.2.pdf` | IREB Requirements Modelling Advanced (DE) |
| `ireb_elicitation_summary.pdf` | IREB Elicitation Summary |
| `requirements_engineering_management.pdf` | RE Management Overview |
| `uml_modellierung_v4.pdf` | UML Modelling |

### Business Analysis

| File | Content |
|---|---|
| `iiba_babok_v3.pdf` | BABOK Guide v3 — IIBA Business Analysis Body of Knowledge |
| `nutzwertanalyse/Nutzwertanalyse.pdf` | Nutzwertanalyse (utility value analysis) |

### Process Management

| File | Content |
|---|---|
| `bpmn_praxishandbuch.pdf` | BPMN Practical Handbook |
| `bpmn_konventionen.pdf` | BPMN Conventions and Standards |

### Project Management

| File | Content |
|---|---|
| `havard_business_review_projectmanagement_guide.PDF` | HBR Project Management Guide |
| `roadmapping_fraunhofer_de.pdf` | Fraunhofer "Praxisstudie Roadmapping" (DE) — roadmap method/practice |
| `backlog_framework_de.pdf` | Agile backlog/Scrum reference (DE) |
| `backlog_framework_en_2.pdf` | Agile backlog & prioritization reference (EN) |
| `frameworks/scrum_framework.pdf` | Scrum framework (agile/backlog source) |

### Governance & Compliance Frameworks

| File | Content |
|---|---|
| `eu_ai_act_en_062024.pdf` | EU AI Act (2024) |
| `eu_gdpr_042016.pdf` | GDPR (2016) |
| `nist_csf_v1.1.pdf` | NIST Cybersecurity Framework v1.1 |
| `nist_sp800_61r2.pdf` | NIST SP 800-61r2 Incident Response |
| `NIST.IR.8596.iprd.pdf` | NIST IR 8596 |
| `aws_well_architected.pdf` | AWS Well-Architected Framework |

**Ingestion rule:** SHA-256 dedup — unchanged frameworks are never re-embedded.
Re-ingest only when a new version of a standard is published.

---

## Phase 1 Capabilities (Portfolio Demo)

### 1. Framework Q&A (RAG)

- User asks any question about the indexed frameworks
- System retrieves relevant chunks and generates a grounded answer with source citations
- Language follows the user's language (DE or EN), since frameworks exist in both
- Example: "What are the BABOK knowledge areas?" → cited answer from BABOK PDF
- Example: "Erkläre den Unterschied zwischen funktionalen und nicht-funktionalen Anforderungen laut IREB"

### 2. Business Problem Structurer

- User provides a business problem description in free text
- System structures it using IREB/BABOK format:
  - Problem Statement
  - Root Cause
  - Affected Stakeholders
  - Business Impact
  - Scope Boundary (In / Out)
- Always marked as "AI-generated draft — requires human review"

### 3. Requirements Structurer

- User pastes raw or unstructured requirements
- System reformats them as INVEST-compliant user stories + Acceptance Criteria
- Flags ambiguous, incomplete, or conflicting requirements
- References the relevant IREB criteria for quality

### 4. Stakeholder Analysis Assistant

- User provides project description + known stakeholders
- System suggests: missing stakeholder categories, RACI matrix skeleton, engagement levels
- Grounded in BABOK stakeholder analysis knowledge area
- Output is a structured starting point, not a final deliverable

---

## Architecture

### Dependency on aiplatform

This project uses `aiplatform` from the `ai-platform-project-v1` repository as a
local pip-installable dependency.

```toml
# pyproject.toml
[project]
dependencies = [
    "aiplatform @ file://../../ai-platform-project-v1",
    ...
]
```

**What is reused from aiplatform:**

| Component | Module | Used for |
|---|---|---|
| PDF Loader | `aiplatform.ingestion.loaders` | Loading all framework PDFs |
| Chunker | `aiplatform.ingestion.chunker` | Splitting into 800-token chunks |
| Embedder | `aiplatform.retrieval.embedder` | OpenAI text-embedding-3-small |
| VectorStore | `aiplatform.retrieval.vector_store` | pgvector similarity search |
| LLM Provider | `aiplatform.llm` | OpenAI / Anthropic (swappable) |
| DB Models | `aiplatform.storage.models` | Document, Chunk, Embedding (app_name="consulting") |
| Settings | `aiplatform.settings` | API keys, DB URL, S3 |

**What is NOT reused (consulting-specific):**

- FastAPI application (`apps/consulting_api/`)
- System prompts (BA/RE/PM domain-specific)
- Artifact structuring logic (`consulting_service.py`)
- Frontend UI (separate branding from platform UI)
- Cognito user pool (consulting demo users)
- Deployment scripts

### Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Mangum |
| Language | Python 3.12 |
| Package manager | uv |
| Vector storage | PostgreSQL + pgvector (shared `ai-platform-db-v2`, `app_name="consulting"`) |
| Embeddings | OpenAI text-embedding-3-small |
| LLM | OpenAI gpt-4o-mini / Anthropic Claude (configurable) |
| Frontend | Next.js (own UI, own branding) |
| Infrastructure | AWS Lambda + API Gateway |
| Auth | Amazon Cognito (own user pool for consulting demo) |

---

## Project Structure

```
ai-consulting-accelerator-project/
├── apps/
│   └── consulting_api/
│       ├── main.py              # FastAPI app + CORS
│       ├── lambda_handler.py    # Mangum adapter
│       ├── api/
│       │   ├── routes.py        # /query, /structure, /sources, /health
│       │   └── schemas.py       # Request/Response models
│       └── services/
│           └── consulting_service.py  # query(), structure_artifact()
├── apps/
│   └── consulting_ui/           # Next.js demo UI
├── data/                        # Framework PDFs (see table above)
│   ├── business_analysis/
│   ├── requirements_engineering/
│   ├── processmanagement/
│   ├── projectmanagement/
│   └── frameworks/
├── scripts/
│   ├── ingest_frameworks.py     # Bulk-ingest all PDFs in data/
│   └── deploy.py                # Lambda + API Gateway deployment
├── research/
│   └── frameworks/              # Notes on each framework, scope decisions
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

---

## Ingestion Pipeline

```bash
# Ingest all frameworks from data/ folder (one-time setup)
uv run python scripts/ingest_frameworks.py --folder data/

# Re-ingest a specific updated framework
uv run python scripts/ingest_frameworks.py --file data/requirements_engineering/cpre_foundationlevel_handbook_en_v1.3.0.pdf
```

Each framework is ingested with metadata:
- `source_uri`: `framework://requirements_engineering/cpre_foundationlevel_handbook_en`
- `app_name`: `consulting`
- `doc_metadata`: `{"category": "requirements_engineering", "language": "en", "standard": "IREB CPRE"}`

---

## Memory Architecture

The system uses two distinct memory layers with different contracts.
Mixing them is the root cause of agent workflow drift (see: procedural vs semantic memory).

### Semantic Memory — Framework Q&A

Implemented as RAG over the vector store (`app_name="consulting"`).

- Query type: "What do I know about X?"
- Match quality: cosine similarity, fuzzy
- Partial match: **feature** — approximate recall is useful
- Used for: Framework Q&A, context lookup, reference retrieval

The LLM synthesises an answer from retrieved chunks. Results are suggestions, not guarantees.

### Procedural Memory — Structuring Skills

Each structuring capability is a **named, versioned skill** with an explicit input/output contract.
Skills are **invoked by name**, never retrieved by similarity.

Skills are grouped into product **layers** (`layer`: discovery | analysis | delivery) —
a taxonomy for the UI/workflow, not separate systems.

| Skill name | Version | Layer | Purpose |
|---|---|---|---|
| `consulting.structure-business-problem` | v1.3 | discovery | Current/target state, pain points, goals, success metrics, root cause, stakeholders, impact, scope |
| `consulting.analyze-stakeholders` | v1.2 | discovery | Role categories, RACI skeleton, influence/interest, engagement levels, communication plan |
| `consulting.identify-risks` | v1.0 | discovery | Risk · Impact · Probability · Recommendation |
| `consulting.detect-assumptions` | v1.0 | discovery | Implicit assumptions to validate |
| `consulting.open-questions` | v1.0 | discovery | Clarification questions before solutioning |
| `consulting.generate-hypotheses` | v1.0 | discovery | Explicitly-labelled root-cause hypotheses |
| `consulting.interview-guide` | v1.0 | discovery | Stakeholder discovery interview guide |
| `consulting.structure-requirements` | v1.3 | analysis | Requirement classification (BR/FR/NFR/…) + INVEST user stories + quality flags |
| `consulting.structure-roadmap` | v1.0 | delivery | Now/Next/Later roadmap + agile backlog (Epic → Feature → User Story) |

**Input contract:** structured user context (defined required fields per skill)
**Output contract:** defined Markdown format, with framework citations
**Trigger:** invoked by name via the API route — not retrieved by embedding similarity
**Versioning:** if the system prompt changes, bump the version (v1.0 → v1.1)

**Why this matters:** two structuring skills with similar purposes (e.g. "structure a problem" and
"structure a scope statement") have high embedding similarity but incompatible output formats.
Retrieval-based invocation would confuse them. Name-based invocation never does.

---

## Prompt Design Principles

All system prompts must:

1. Ground answers in retrieved framework chunks — cite `[1]`, `[2]` labels explicitly
2. Clearly mark outputs as "AI-generated draft — requires human review"
3. State limitations explicitly: "This is a starting point, not a final deliverable"
4. Never claim expertise beyond what the retrieved context supports
5. Acknowledge when the framework does not cover the user's question
6. Follow the user's language (DE or EN) — frameworks exist in both
7. For structuring tasks: produce clean, copy-pasteable output in Markdown or structured format

---

## Cost Controls

| Item | Cost |
|---|---|
| Framework ingestion (one-time, ~20 PDFs) | ~$2–5 total |
| Query (embedding + LLM per question) | ~$0.01–0.02 |
| No scheduled pipelines — user-triggered only | — |
| Frameworks are permanent — no retention rule needed | — |
| Monthly operational target | < $5/month |

---

## Engineering Principles

Inherited from ai-platform-project-v1:
- Modular and reusable architecture
- SHA-256 dedup — never re-embed unchanged documents
- Source attribution on all generated content
- Cost-aware LLM usage — only relevant chunks sent to LLM
- No vendor lock-in — LLM provider swappable via `LLM_PROVIDER` env var
- Separation of ingestion phase from query phase

Consulting-specific additions:
- Every AI output must cite the framework section it references; where a framework does
  not back the content (e.g. estimation), label it **indicative/heuristic** — never fabricate citations
- **Output language is locked to the input language** (DE/EN), detected server-side and
  passed as an explicit instruction — grounding context in another language must never
  flip the output language
- Structured input → structured output (no open-ended generation without user context)
- All artifact templates are versioned and reviewable
- Never produce outputs that could be mistaken for professional consulting advice
- Human review is required before any structured artifact is used in a real project
- **Confidentiality:** persisted client engagement data (Phase 2 interview mode) must use
  an isolated DB — never the shared public `ai-platform-db-v2`

---

## Preferred Working Style

Same as ai-platform-project-v1:
- Show plan before executing complex tasks
- Practical and production-oriented outputs
- Bullet points over paragraphs
- No overengineering
- Ask clarifying questions before starting a new feature

---

## Roadmap

### Phase 1 — Portfolio Demo (current)

- Ingest all frameworks from `data/` folder
- Framework Q&A (RAG with source citations)
- Business Problem Structurer (IREB/BABOK format)
- Requirements Structurer (INVEST + Acceptance Criteria)
- Stakeholder Analysis Assistant
- Roadmap Generator (Now/Next/Later + agile backlog) — grounded in roadmapping + Scrum
- Next.js demo UI (sidebar app, dark platform theme) at consulting.bridging-data.com
- **Public demo — no auth in Phase 1** (Cognito deferred; UI calls the public
  `/api/v1/consulting/*` routes)

### Phase 2 — Practitioner Toolset (optional, 2027)

- Process Model Assistant (BPMN notation, conventions from `bpmn_konventionen.pdf`)
- Project Charter Generator (HBR PMBOK-aligned)
- Agile Artifact Generator (Sprint Goals, Definition of Done, Backlog items)
- DE/EN language toggle (leverages bilingual framework PDFs already available)

### Phase 3 — Client-Facing SaaS (optional, future)

- Multi-tenant architecture (each client = isolated workspace)
- Database: separate `ai-platform-db-consulting` RDS instance required — `ai-platform-db-v2` is shared public infrastructure, not suitable for client data isolation
- Project history and artifact versioning
- Export to Word / PDF
- Custom framework upload per client

---

## Scope Boundary — What Belongs in This Repo

| In scope | Out of scope |
|---|---|
| Framework Q&A and RAG | Intelligence synthesis (→ ai-platform-project-v1 Phase 7) |
| BA/RE/PM artifact structuring | Technology Radar, Competitor Radar, Regulatory Radar |
| Consulting-domain prompts | Corporate LLM (→ ai-platform-project-v1 Phase 6) |
| Portfolio demo UI | Signal collection pipelines |
| Framework ingestion scripts | LinkedIn content creation |
