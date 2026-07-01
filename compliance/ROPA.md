# Record of Processing Activities (ROPA)

**Regulation:** GDPR Art. 30 / Swiss DSG
**System:** AI Consulting Accelerator — private single-admin demo (consulting.bridging-data.com)
**Last updated:** July 2026

> This ROPA reflects a **portfolio demo**. By design it processes **no third-party personal data**:
> the corpus is public industry standards and the owner's own internal knowledge, and the only account
> is the single admin. Personal data would only enter if a user pastes it into a free-text input;
> before any real client engagement data is stored, the isolated engagement DB (gap G1) must be in
> place and a proper controller/processor agreement established.

---

## Controller Details

| Field | Value |
|---|---|
| Controller | bridging-data.com (sole operator) |
| Contact | <OWNER_EMAIL> |
| Hosting region | AWS eu-central-1 (Frankfurt) |
| Role | Controller for the demo; would become Processor if operated for a client (needs a DPA) |

---

## Processing Activity 1 — Framework Q&A (RAG)
| Field | Detail |
|---|---|
| Purpose | Answer questions grounded in indexed industry frameworks, with citations |
| Legal basis | Legitimate interest (own portfolio demo over public standards) |
| Data categories | Public framework text (IREB/BABOK/BPMN/… — no personal data); the user's free-text question |
| Data subjects | None by design (the admin is the only user) |
| Storage | `ai-platform-db-v2`, `app_name="consulting"` (documents/chunks/embeddings) — encrypted, VPC-private |
| Retention | Framework corpus permanent (re-ingested only on new standard versions); queries not persisted |
| Recipients / processors | OpenAI (query + chunks sent for embedding/inference) |

## Processing Activity 2 — Structuring Skills
| Field | Detail |
|---|---|
| Purpose | Turn free-text business context into framework-aligned drafts (14 named skills) |
| Legal basis | Legitimate interest (demo) |
| Data categories | User-entered business situation text (may contain personal data **if the user includes it**) |
| Data subjects | Whoever the user chooses to describe (admin-controlled; test data only today) |
| Storage | Not persisted for one-shot skills — request/response only; result returned to the browser |
| Retention | None (transient) |
| Recipients / processors | OpenAI (prompt sent for inference) |

## Processing Activity 3 — Engagements (multi-round discovery)
| Field | Detail |
|---|---|
| Purpose | Stateful discovery → analysis: initial input, rounds, requirements, assessment, downstream artifacts |
| Legal basis | Legitimate interest (demo); a real client engagement would require a DPA |
| Data categories | User-entered situation + answer text (free text — potentially personal/confidential if included) |
| Data subjects | Admin's test scenarios today; potentially client stakeholders if real data were entered |
| Storage | `consulting_engagements` table (JSONB `turns`/`extras`). **Currently in the shared `db-v2` — not isolated (gap G1).** Encrypted at rest, VPC-private |
| Retention | Kept until deleted via the lifecycle **delete** (GDPR Art. 17 erasure); no automated retention rule |
| Recipients / processors | OpenAI (round content sent for inference) |

## Processing Activity 4 — Organizational Memory (skills & projects)
| Field | Detail |
|---|---|
| Purpose | Retrieve relevant existing internal knowledge as cited references (never invents) |
| Legal basis | Legitimate interest (own internal, non-confidential knowledge) |
| Data categories | Own toolkit skills + own project READMEs; may mention the owner's email as author metadata |
| Data subjects | The owner only |
| Storage | `ai-platform-db-v2`, `app_name="skills"` / `"projects"` — encrypted, VPC-private |
| Retention | Permanent; refreshed by re-ingest (SHA-256 dedup); no client data ever mixed in |
| Recipients / processors | OpenAI (embeddings + a one-line description generation) |

---

## Sub-Processors

| Processor | Purpose | Location | Notes |
|---|---|---|---|
| OpenAI | Embeddings (`text-embedding-3-small`) + LLM inference (`gpt-4o-mini`) | US | Receives query/prompt/chunk content at request time; API usage not used for training per OpenAI API terms |
| Amazon Web Services | Hosting (Lambda, API Gateway, RDS, S3, CloudFront, Cognito) | eu-central-1 (Frankfurt) | Data at rest stays in-region; encrypted |

---

## Data Subject Rights

| Right | Support |
|---|---|
| Erasure (Art. 17) | Engagement **delete** (cascades the record); framework/OM corpus is non-personal |
| Access (Art. 15) | Engagement list/detail + report export (md/docx/pdf) |
| Portability (Art. 20) | Report export covers engagement content |
| Object (Art. 21) | Not implemented — single-admin context |
| Rectification (Art. 16) | Re-run/edit the engagement input; SHA-256 dedup re-indexes changed source docs |

---

## Review Schedule

Review this ROPA when: a new processing activity or data source is added, a new sub-processor is
introduced, or **before** real client engagement data is first stored (which also requires closing
gap G1 — an isolated engagement DB — and a controller/processor agreement).
