# Model Card — AI Consulting Accelerator

**System:** AI-assisted BA/RE/PM consulting workflow (Discovery → Analysis → Delivery)
**Deployment:** Private single-admin demo — consulting.bridging-data.com
**Last updated:** July 2026
**Owner:** <OWNER_EMAIL>

> The platform uses third-party foundation models via API; it does **not** train, fine-tune, or host
> its own models. This card documents the models used, their intended use, and their limitations.

---

## 1. Model Overview

### Embedding Model
- **Model:** OpenAI `text-embedding-3-small` (1536-dimensional)
- **Purpose:** Embed framework chunks + user queries for pgvector similarity search (RAG retrieval)
  and Organizational Memory retrieval.
- **Configurable:** `OPENAI_EMBEDDING_MODEL` / `OPENAI_EMBEDDING_DIMENSIONS` (`aiplatform.settings`).

### LLM — Framework Q&A (RAG)
- **Model:** OpenAI `gpt-4o-mini` (default)
- **Purpose:** Answer questions grounded **only** in retrieved, cited framework chunks (IREB, BABOK,
  BPMN, PMBOK/HBR, Scrum, EU AI Act, GDPR, NIST, AWS WA).
- **Behaviour:** Answers cite sources (`[1]`, `[2]` → `source_uri`); the prompt forbids unsupported
  claims and instructs the model to say when the frameworks don't cover a question.

### LLM — Structuring Skills & Engagements
- **Model:** OpenAI `gpt-4o-mini` (default)
- **Purpose:** Run the 14 named, versioned skills (`services/skills.py`) — business-problem,
  stakeholders, risks, requirements (INVEST), roadmap, consultant assessment, compliance maturity,
  etc. — and the multi-round engagement flow (discovery → analysis → conclude).
- **Behaviour:** Structured input → structured Markdown draft; output language locked to input;
  every output ends with a review disclaimer.

**Provider is swappable** (no vendor lock-in): `LLM_PROVIDER=openai|anthropic` selects the backend;
`OPENAI_CHAT_MODEL` overrides the model. Embeddings are OpenAI in the current deployment.

---

## 2. Intended Use

- Accelerate BA/RE/PM structuring work: turn free-text situations into framework-aligned drafts
  (problem definition, stakeholders, risks, requirements, roadmap, compliance maturity).
- Answer questions about the indexed industry frameworks with citations.
- Demonstrate to prospects how AI accelerates consulting **workflow** — every output a draft for a
  qualified human to review.

**Core principle:** *AI assists; it does not replace human judgment.*

## 3. Out-of-Scope Uses

- Not a producer of final professional deliverables (all outputs are review drafts).
- Not legal, financial, or compliance advice (incl. the `compliance.assess-maturity` skill — it is an
  assist for a qualified advisor, not a determination).
- Not an autonomous requirements generator (no structured input → no useful output).
- Not a decision-maker, and not a cost estimator without detailed project data.
- Not for storing real client personal/confidential data until the isolated engagement DB exists
  (see `SECURITY_CONTROLS.md` gap G1).

## 4. Known Limitations

| Limitation | Mitigation |
|---|---|
| LLM hallucination / fabrication | RAG-only grounding, mandatory citations, prompts forbid unsupported claims; outputs are drafts |
| LLM classification/generation bias | Not formally evaluated (documented gap); human review required |
| Framework coverage: 23 of 26 PDFs indexed | 3 oversized PDFs (`requirements_engineering_management` 74 MB, `uml_modellierung_v4`, `aws_well_architected`) exceed the Lambda ingest limits; RE is otherwise covered by the four IREB handbooks |
| Language | Output is locked to the **input** language (DE/EN); grounding context in another language must not flip it |
| No real-time / web knowledge | Answers reflect only the ingested framework corpus (permanent; re-ingested only on new standard versions) |
| Output quality depends on input quality | Structured, specific input yields useful drafts; vague input is flagged as "not enough information" |
| Single-shot per skill | Each skill is one grounded generation; the engagement flow adds multi-round refinement |

## 5. Evaluation & Monitoring

- **Quality eval harness:** `scripts/eval.py` runs golden cases (DE/EN, across skills) through the
  real skills and applies rule-based checks (`services/eval_checks.py`): non-empty, language lock,
  draft disclaimer, structure, required sections, preliminary-framing caveats, citation integrity.
- **Opt-in LLM-as-judge:** `eval.py --judge` scores groundedness / relevance / citation faithfulness
  (advisory, non-gating).
- **Monitoring:** CloudWatch logs for the Lambda; per-run LLM/embedding call caps; cost target < $5/mo.
- Run the harness after any prompt or model change (it calls the real LLM — a few cents per run).

## 6. Provider Configuration

| Setting | Value (deployment) |
|---|---|
| `LLM_PROVIDER` | `openai` |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` (1536-dim) |
| Secrets | API key from the Lambda environment (never committed; see `SECURITY_CONTROLS.md`) |

OpenAI acts as an Art. 28 processor for prompt/query content sent for inference — see `ROPA.md`.

## 7. Disclaimers

- Every generated artifact is an **AI-generated draft that requires human review** — never a final
  professional deliverable.
- The platform structures information; **humans decide**.
- Outputs must not be presented as legal, financial, or compliance determinations.
- Framework citations ground terminology; where a framework does not back a statement, the output
  labels it as indicative/heuristic and never fabricates a citation.
