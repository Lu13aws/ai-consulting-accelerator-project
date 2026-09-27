# Framework corpus — not included in this repository

`data/` is where `scripts/ingest_frameworks.py` looks for the industry-standard documents that get
indexed under `app_name="consulting"`. Almost all of them are copyrighted third-party material
(purchased handbooks, standards-body PDFs, a licensed course), so **the files themselves are not
tracked in this repository or its history** — only this README and `data/patterns/*.md` (the
platform owner's own notes) are. Provide your own copies locally before running the ingest script;
see `DEPLOY.md` for the full ingest procedure.

`scripts/ingest_frameworks.py` derives each document's `source_uri` from its folder, as
`framework://<category>/<filename-stem>` — so the folder layout below is not just organisational,
it is part of the citation the chat shows. Keep files under the same category folders.

## Expected sources

| Category folder | Document | Where to obtain it |
|---|---|---|
| `business_analysis/` | BABOK Guide v3 | IIBA membership (babok.iiba.org) — not redistributable |
| `requirements_engineering/` | IREB CPRE Foundation Level Handbook (EN/DE) | ireb.org — free registration |
| `requirements_engineering/` | IREB CPRE Advanced Level Handbook — Elicitation (EN/DE) | ireb.org |
| `requirements_engineering/` | IREB CPRE Advanced Level Handbook — Requirements Modeling (EN/DE) | ireb.org |
| `requirements_engineering/` | IREB CPRE Handbook for Requirements Management (EN/DE) | ireb.org |
| `requirements_engineering/` | A UML modelling reference | own course material — not redistributable |
| `requirements_engineering/` | A requirements-engineering management text | own course material — not redistributable |
| `projectmanagement/` | An HBR project-management guide | Harvard Business Review — purchased, not redistributable |
| `projectmanagement/` | A backlog-framework guide (EN/DE) | own course material |
| `projectmanagement/` | A roadmapping guide (Fraunhofer) | Fraunhofer publication |
| `processmanagement/` | BPMN conventions and practitioner's handbook | own course material |
| `frameworks/` | EU AI Act (consolidated text) | eur-lex.europa.eu — public domain |
| `frameworks/` | EU GDPR (consolidated text) | eur-lex.europa.eu — public domain |
| `frameworks/` | NIST Cybersecurity Framework 1.1 | nist.gov — public domain (US government work) |
| `frameworks/` | NIST SP 800-61r2 (incident handling) | nist.gov — public domain |
| `frameworks/` | NIST IR 8596 | nist.gov — public domain |
| `frameworks/` | AWS Well-Architected Framework | aws.amazon.com — freely available, but redistribution terms were not checked |
| `frameworks/` | A Scrum framework reference | own course material |
| `business_analysis/nutzwertanalyse/` | A weighted decision-matrix ("Nutzwertanalyse") course exercise, including two `.docx` write-ups, a `.pptx` and reference screenshots | own course material — not redistributable |

## What is tracked instead

- `data/patterns/*.md` — the owner's own pattern notes (`ai_document_processing.md`,
  `corporate_knowledge_hub.md`, `enterprise_search.md`). These are original writing, not third-party
  material, so they stay in the repository.
- This file.

## Indexed content — an operating constraint, not just a note

23 of the documents above are indexed in the production database (`app_name="consulting"`; three
oversized PDFs are skipped, see `DEPLOY.md`). The deployed chat answers questions by quoting short,
cited excerpts from that index.

**This is why every `/api/v1/*` route of this API requires a signed-in admin token (Cognito JWT),
with no public, unauthenticated route added.** A public route would let anyone retrieve excerpts of
copyrighted material through the chat — that would be redistribution, not a citation. Whoever
operates a deployment of this project is responsible for keeping the API private (or re-scoping the
indexed corpus to material they are allowed to redistribute) before exposing any route publicly.

## Setup

```bash
uv run python scripts/ingest_frameworks.py --dry-run   # lists what it would index, no writes
uv run python scripts/ingest_frameworks.py             # bulk-ingest everything under data/
```

Running the script against an empty or incomplete `data/` folder does not silently succeed — it
exits with an error pointing back to this file.
