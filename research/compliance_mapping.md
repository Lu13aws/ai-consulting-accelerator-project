# Compliance Mapping — AI Consulting Accelerator

**Use case:** AI-assisted BA/RE/PM consulting workflow — private single-admin portfolio demo
(consulting.bridging-data.com)
**Data:** Public framework PDFs (IREB, BABOK, BPMN, PMBOK, Scrum…), own internal knowledge
(skills, project READMEs), and user-entered engagement text (business situations)
**Assessment date:** July 2026; re-verified against the code and the AWS account on 2026-09-26 (see `../compliance/CLAIMS_VERIFICATION.md`)
**Assessed by:** Evidence-based review of this repo against the three target frameworks (mirrors the
approach in `../ai-platform-project-v1/research/phase6/compliance_mapping_v2.md`)
**Frameworks:** NIST AI RMF · GDPR / Swiss DSG · AWS Well-Architected (Security Pillar)

> This is an internal engineering self-assessment for a demo, **not** legal compliance
> documentation and **not** legal advice. Client engagement data is out of scope until an isolated
> engagement DB is provisioned (see Gap G1).

---

## Executive Summary

The platform has a **solid security baseline for a demo** — single-admin Cognito auth enforced at the
API-Gateway edge, private VPC, encryption at rest and in transit, secrets kept out of git — and
**strong AI-assurance controls**: every answer is grounded in cited framework chunks, every skill
output carries a review disclaimer, the output language is locked to the input, and a rule-based +
LLM-judge eval harness guards quality.

The **material gap is data isolation**: consulting content **and** engagement records currently live
in the **shared** `ai-platform-db-v2` (scoped only by `app_name`), not an isolated database. This is
acceptable while the only user is the admin entering test data, but must be closed before any real
client engagement data is stored (CLAUDE.md already states this).

| Framework | Coverage (implemented) | After the 3 compliance docs |
|---|---|---|
| NIST AI RMF | 78 % (15.5 / 20) | 80 % (16 / 20) |
| GDPR / Swiss DSG | 64 % (11.5 / 18) | 72 % (13 / 18) |
| AWS Well-Architected (Security) | 67 % (10 / 15) | 63 % (9.5 / 15) |

*Corrected 2026-09-26: the GDPR "after docs" value was 13.5 / 18 but the tables only support 13 / 18 (Art. 30: three partial rows become done). The AWS value was 10.5 / 15 with no supporting row; the docs do not change it, and the credentials control drops to partial (plaintext environment variables), giving 9.5 / 15.*

**Scoring method (transparent, not hand-waved):** each figure is the sum over the requirement tables
below of ✅ Done = 1, ⚠️ Partial = 0.5, ❌ Missing = 0, divided by the N requirements assessed for that
framework. The 3 planned documents (`compliance/MODEL_CARD.md`, `ROPA.md`, `SECURITY_CONTROLS.md`)
raise the score **only** where they close a genuine *documentation* gap (model card, records of
processing, controls-evidence map). They deliberately do **not** move architectural/operational gaps
(G1 isolated DB, G2 audit log, G3 WAF), which stay open and are tracked below — so the "after docs"
figures are modest by design.

---

## Implemented controls (evidence base)

| Control | Implementation | Compliance relevance |
|---|---|---|
| Single-admin authentication | Cognito pool `<COGNITO_USER_POOL_ID>`, self-signup off (`AllowAdminCreateUserOnly`, `scripts/setup_consulting_cognito.py`) | Access control, identity |
| Edge auth enforcement | API Gateway JWT authorizer on `$default`; only `GET /health` + CORS-preflight `OPTIONS` are public (`scripts/deploy.py` ROUTE_CONFIGS) | Auth before the app runs |
| Network isolation | Lambda + RDS in `<VPC_ID>`; `ai-platform-db-v2` `PubliclyAccessible=false` | Infrastructure protection |
| Encryption | RDS `StorageEncrypted=true`; TLS/HTTPS everywhere; DB `ssl/sslmode=require` | GDPR Art.32, WA Data Protection |
| Secrets management | `.env` + `infra/deploy.env` gitignored, never committed; injected as Lambda environment variables at deploy (plaintext in the function configuration, gap G8) | No hardcoded credentials in git |
| Source attribution | `SourceReference{chunk_id, source_uri, score}` returned per answer (`api/schemas.py`, `consulting_service.py`) | NIST MEASURE, transparency |
| Grounded generation | RAG-only answers over cited chunks; prompts forbid unsupported claims | Hallucination mitigation |
| Output-language lock | `_LANG_RULE` in every skill (`services/skills.py`); enforced by tests | Faithfulness, EU-language use |
| Review disclaimers | `DRAFT_DISCLAIMER` + per-skill "requires human review"; "AI assists — humans decide" (CLAUDE.md) | Human oversight (NIST MANAGE) |
| Quality eval harness | `scripts/eval.py` + `services/eval_checks.py` (rule-based) + opt-in LLM-judge | Performance/quality review |
| Deduplication | SHA-256 `content_hash` (unique) — unchanged docs never re-embedded | Accuracy, cost control |
| Data deletion | `EngagementService.delete()` + UI lifecycle delete | GDPR Art.17 erasure |
| Compliance self-assessment | `compliance.assess-maturity` skill (this platform can assess AI projects, incl. itself) | GOVERN tooling |

---

## 1. NIST AI Risk Management Framework

### GOVERN — Policies, Accountability, Risk Tolerance
| Requirement | Status | Evidence |
|---|---|---|
| Define AI system purpose & scope | ✅ Done | CLAUDE.md — purpose, "What this is / is NOT", scope boundary |
| Assign accountability for AI outputs | ✅ Done | Single owner (admin); every output a draft for human review |
| Acceptable-use / non-goals | ✅ Done | CLAUDE.md "What This Product Is NOT" (not legal/decision-maker) |
| Document model + version | ⚠️ Partial | Provider/model in `settings`; no model card yet → `MODEL_CARD.md` |
| Risk tolerance policy | ⚠️ Partial | Cost caps + demo scope; no formal AI-risk policy |
| Review cadence | ⚠️ Partial | Eval harness on demand; no scheduled review process |

### MAP — Context & Risk Identification
| Requirement | Status | Evidence |
|---|---|---|
| Identify stakeholders | ✅ Done | CLAUDE.md Target Audience |
| Data sources & provenance | ✅ Done | `source_uri` per chunk; `framework://` / `skill://` / `project://` URIs |
| Document assumptions & limitations | ✅ Done | Prompts flag "not enough information", "to validate"; disclaimers |
| Potential-harms register | ⚠️ Partial | RAG grounding + disclaimers reduce risk; no formal harm register |

### MEASURE — Risk Analysis
| Requirement | Status | Evidence |
|---|---|---|
| Source attribution on answers | ✅ Done | `SourceReference` with similarity score on every response |
| Confidence / similarity scoring | ✅ Done | `score` per source; retrieval threshold filtering |
| Hallucination mitigation | ✅ Done | RAG-only; prompts forbid unsupported claims; citations required |
| Quality evaluation | ✅ Done | `eval.py` golden cases + rule checks + opt-in LLM-judge |
| Cost monitoring | ✅ Done | `MAX_CHUNKS_PER_DOC`, per-run LLM/embedding caps; <$5/mo target |
| Bias assessment | ❌ Missing | LLM classification bias not formally evaluated |

### MANAGE — Risk Response & Monitoring
| Requirement | Status | Evidence |
|---|---|---|
| Human review before use | ✅ Done | Every artifact a review draft; engagements are advisory |
| Data deletion | ✅ Done | Engagement delete (Art.17); frameworks permanent by design |
| Incident response plan | ❌ Missing | No documented process (out of core-3 doc set) |
| Monitoring & alerting | ⚠️ Partial | CloudWatch logs; no app-level audit trail or drift alerts |

---

## 2. GDPR / Swiss DSG

### Processing Principles (Art. 5)
| Principle | Status | Evidence |
|---|---|---|
| Lawfulness | ✅ Done | Public standards + own internal docs (legitimate interest); no third-party PII by design |
| Purpose limitation | ✅ Done | `app_name="consulting"` scoping; engagement engine separate from RAG session |
| Data minimisation | ✅ Done | Only chunks + minimal metadata; no accounts/profiles beyond the one admin |
| Accuracy | ✅ Done | SHA-256 dedup; versioned skills |
| Storage limitation | ⚠️ Partial | Engagement delete exists; no automated retention for engagement text |
| Integrity & confidentiality | ⚠️ Partial | Encryption + TLS + single-admin auth — but **shared DB, not isolated** (Gap G1) |

### Individual Rights
| Right | Status | Evidence |
|---|---|---|
| Erasure (Art.17) | ✅ Done | `EngagementService.delete()` + UI delete |
| Access (Art.15) | ⚠️ Partial | Engagement list/detail + report export; no formal "all my data" API |
| Portability (Art.20) | ⚠️ Partial | Report export (md/docx/pdf) covers engagement export |
| Object (Art.21) | ❌ Missing | No opt-out mechanism (single-admin context) |

### Technical & Organizational Measures (Art. 32)
| Measure | Status | Evidence |
|---|---|---|
| Encryption at rest | ✅ Done | `ai-platform-db-v2` `StorageEncrypted=true` |
| Encryption in transit | ✅ Done | HTTPS (API GW/CloudFront); `ssl/sslmode=require` for RDS |
| Access control | ✅ Done | Cognito single-admin; JWT authorizer at edge |
| Audit logging | ❌ Missing | No per-action audit log (single-admin partially mitigates) |
| Breach notification process | ❌ Missing | Not documented (out of core-3 doc set) |

### Records of Processing (Art. 30)
| Requirement | Status | Evidence |
|---|---|---|
| What data is processed | ⚠️ Partial | Documented in CLAUDE.md → formalised in `ROPA.md` |
| Retention periods | ⚠️ Partial | Frameworks permanent; engagement text ad-hoc → `ROPA.md` |
| Processors (Art.28) | ⚠️ Partial | OpenAI (embeddings + LLM) used; noted in `ROPA.md` (no separate PROCESSORS.md in core set) |

---

## 3. AWS Well-Architected — Security Pillar

### Identity & Access Management
| Control | Status | Evidence |
|---|---|---|
| Least-privilege IAM role | ✅ Done | `ai-consulting-lambda-role` (basic + VPC execution) |
| No hardcoded credentials | ⚠️ Partial | Not in git (history checked); but stored as plaintext Lambda environment variables instead of Secrets Manager (Gap G8) |
| End-user authentication | ✅ Done | Cognito JWT authorizer on all `/api/v1/*` routes |
| Single-admin access | ✅ Done | Self-signup disabled; one admin user |

### Infrastructure Protection
| Control | Status | Evidence |
|---|---|---|
| RDS in private VPC | ✅ Done | `<VPC_ID>`, no public endpoint |
| Security groups scoped | ✅ Done | DB reachable from the Lambda SG (platform-managed) |
| WAF on API Gateway | ❌ Missing | No WAF (cannot be attached to HTTP APIs); default route throttling of 10 req/s, burst 20 since 2026-09-26 (Gap G3) |
| Physical data isolation | ⚠️ Partial | **Shared `db-v2`; consulting + engagements not isolated** (Gap G1) |

### Data Protection
| Control | Status | Evidence |
|---|---|---|
| Encryption at rest / in transit | ✅ Done | RDS encrypted; TLS everywhere |
| Data classification | ⚠️ Partial | `app_name` acts as a soft classifier; no formal policy |
| Separate storage per class | ❌ Missing | Public frameworks + internal OM + engagement text share one DB (Gap G1) |

### Detection & Monitoring
| Control | Status | Evidence |
|---|---|---|
| CloudWatch logs | ✅ Done | Lambda logs (`/aws/lambda/ai-consulting-api`) |
| Cost alerts / caps | ✅ Done | Per-run caps; the account has one shared AWS budget (50 USD, exceeded by the platform's fixed costs); no app-specific alert |
| Application audit trail | ❌ Missing | No audit log (Gap G2) |
| Infra anomaly detection | ❌ Missing | No GuardDuty, no CloudTrail trail, no CloudWatch alarms (demo-acceptable) |

---

## Gaps & Recommendations

Severity reflects impact **in this demo context today**; the "Trigger" column is the concrete event
that turns a gap into a must-fix. G1 is the single hard gate — everything else is either resolved by
this effort (G4–G6) or demo-acceptable until a scale/data trigger fires (G2, G3, G7).

| ID | Gap | Severity (today) | Trigger — must fix when… | Action |
|---|---|---|---|---|
| **G1** | Consulting **and** engagement data share `db-v2` (only `app_name`-scoped), not an isolated DB | **Critical (latent)** — low now (admin test data only), critical the moment real data lands | …a real client's engagement text (potentially personal/confidential) is entered | Point `CONSULTING_ENGAGEMENT_DB_URL` at a **separate encrypted RDS** in-VPC; migrate the `consulting_engagements` table. **Hard gate before any real engagement.** |
| G2 | No application audit log (who did what, when) | Medium | …a second user exists, or real data is processed (GDPR Art.32/Art.30 accountability) | Add an `audit_log` (user, action, resource, ip, ts) — mirror the platform's `AuditLog` |
| G3 | No WAF (not available for HTTP APIs); default route throttling only (10 req/s, burst 20) | Low | …the API is exposed beyond the single admin, or abuse/cost spikes appear | Attach AWS WAF (rate limiting + managed rules) to the API Gateway |
| G4 | No model card | Low | — (documentation) | ✅ Resolved by `compliance/MODEL_CARD.md` (this effort) |
| G5 | No records of processing (ROPA) | Low | — (documentation) | ✅ Resolved by `compliance/ROPA.md` (this effort) |
| G6 | No controls-evidence map | Low | — (documentation) | ✅ Resolved by `compliance/SECURITY_CONTROLS.md` (this effort) |
| G7 | No bias assessment, incident-response, or 72h breach process | Low | …the platform moves toward production / real users | Document when production-bound (out of the core-3 doc scope) |
| G8 | Secrets are plaintext Lambda environment variables, not Secrets Manager | Medium | …before real data, or before the account is shared | Store `OPENAI_API_KEY` and the DB URLs in Secrets Manager and load them at cold start |
| G9 | No MFA on the Cognito admin; no CloudTrail trail, alarms or API access logs | Medium | …a second user exists, or real data is processed | Enable TOTP MFA; create a trail; alarms on Lambda errors and 5xx |

---

## Conclusion & Maturity Level

Assessed on the same ladder the `compliance.assess-maturity` skill applies:

| Level | Verdict | Basis |
|---|---|---|
| **Demo-Ready** | ✅ Yes, today | Edge auth + VPC + encryption + secrets hygiene; AI-assurance (citations, language-lock, disclaimers, eval). Safe on the private single-admin URL. |
| **Customer-Ready** | 🟡 Partial | Fine to demo the workflow live to a prospect (owner logs in and screen-shares). **Not** for a prospect entering their own real data — that trips G1. |
| **Production-Ready** | ❌ No | Needs G1 (isolated engagement DB) → then G2 (audit log) + G3 (WAF), plus G7 (bias/incident/breach docs). |

**Bottom line:** a credible, compliance-aware **demo** that honestly produces review drafts, never
professional deliverables. The three documents produced with this mapping close the documentation gaps
(G4–G6) and make the posture explicit; **G1 is the single hard gate** before any real client engagement
data may be stored.
