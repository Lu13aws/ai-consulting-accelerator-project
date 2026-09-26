# Security Controls — Evidence Map

**System:** AI Consulting Accelerator — private single-admin demo
**Last updated:** July 2026; technical statements re-checked against the code and the AWS account on 2026-09-26 (see `CLAIMS_VERIFICATION.md`)
**Companion to:** `../research/compliance_mapping.md` (full framework assessment)

Each control below maps an implemented measure to the framework requirement it satisfies, with
concrete evidence. Known gaps are listed honestly in §8.

---

## 1. Authentication & Access Control
| Control | Evidence | Satisfies |
|---|---|---|
| Single-admin identity, no self-signup | Cognito pool `<COGNITO_USER_POOL_ID>`, `AllowAdminCreateUserOnly`, one confirmed user, MFA off (`scripts/setup_consulting_cognito.py`) | GDPR Art.32, WA IAM |
| Auth enforced at the edge | API Gateway JWT authorizer on `$default`; only `GET /health` + CORS-preflight `OPTIONS` public (`scripts/deploy.py`). Any valid token of the pool is accepted (no group check): safe only because the pool has a single admin and no self-signup | NIST GOVERN, WA IAM |
| Rate limiting | API Gateway default route throttling of 10 requests/s, burst 20 (set 2026-09-26) | WA Detection/Protection |
| Least-privilege compute role | `ai-consulting-lambda-role` (basic + VPC execution only) | WA IAM |
| No hardcoded credentials in git | `.env` + `infra/deploy.env` gitignored and never committed (full history checked 2026-09-26). The secrets (`OPENAI_API_KEY`, `DATABASE_URL`, `ALEMBIC_DATABASE_URL`) are injected as Lambda environment variables, i.e. stored in plaintext in the function configuration, not in Secrets Manager (gap G8) | WA IAM (partial), Art.32 |

## 2. Data Isolation
| Control | Evidence | Satisfies |
|---|---|---|
| Application scoping | `app_name="consulting"` / `"skills"` / `"projects"` on every `documents` row (the `consulting_engagements` table has no `app_name` column) | Purpose limitation (Art.5) |
| Network isolation | RDS `ai-platform-db-v2` `PubliclyAccessible=false`, in `<VPC_ID>`; only the Lambda security group may connect | WA Infrastructure Protection |
| Dedicated engagement engine (code path) | `CONSULTING_ENGAGEMENT_DB_URL` via a separate SQLAlchemy engine (`storage/engagement_db.py`). The variable is **not set in production** (checked 2026-09-26), so the engine falls back to `DATABASE_URL` = shared `db-v2` | Confidentiality (Art.32) |
| ⚠️ Physical DB isolation | **Not yet** — consulting + engagement data share `db-v2` (see gap G1) | — |

## 3. Data Encryption
| Control | Evidence | Satisfies |
|---|---|---|
| Encryption at rest | RDS `StorageEncrypted=true` (verified via AWS CLI) | Art.32, WA Data Protection |
| Encryption in transit | HTTPS (API Gateway + CloudFront); the DB connection URLs request SSL and the default PostgreSQL 16 parameter group enforces it (`rds.force_ssl=1`) | Art.32, WA Data Protection |
| HTTPS frontend | CloudFront with ACM cert (redirect to HTTPS, TLS 1.2 minimum); custom domain `consulting.bridging-data.com`. The S3 origin is a public website endpoint (bucket policy allows public `GetObject`), so the static UI files are also reachable over plain HTTP directly from S3; they contain no secrets | Art.32 |

## 4. Audit Logging
| Control | Evidence | Satisfies |
|---|---|---|
| Infrastructure logs | CloudWatch logs for `ai-consulting-api` Lambda, 30-day retention (set 2026-09-26); no CloudWatch alarms, no API access logging, no CloudTrail trail | WA Detection (partial) |
| ⚠️ Per-user action audit trail | **Missing** (see gap G2) — single-admin partially mitigates | GDPR Art.30/32 (partial) |

## 5. Data Lifecycle & Retention
| Control | Evidence | Satisfies |
|---|---|---|
| Right to erasure | Engagement lifecycle **delete** cascades the record | GDPR Art.17 |
| Deduplication (accuracy) | SHA-256 `content_hash` (unique) — unchanged docs never re-embedded | Art.5 accuracy |
| Framework permanence | Corpus re-ingested only on new standard versions | Storage limitation (scoped) |
| ⚠️ Automated engagement retention | Not implemented — deletion is manual | Storage limitation (partial) |

## 6. AI-Specific Controls
| Control | Evidence | Satisfies |
|---|---|---|
| Grounded, cited answers | RAG-only over retrieved chunks; `SourceReference{source_uri, score}` per answer | NIST MAP/MEASURE |
| Hallucination mitigation | Prompts forbid unsupported claims; citations required; "say when frameworks don't cover it" | NIST MEASURE |
| Output-language lock | `_LANG_RULE` in every skill; enforced by unit tests | Faithfulness |
| Human-oversight framing | `DRAFT_DISCLAIMER` + per-skill review notice; "AI assists — humans decide" | NIST MANAGE |
| Named, versioned skills | `services/skills.py` registry; invoked by name, not similarity | Governance / reproducibility |
| Quality evaluation | `scripts/eval.py` + `services/eval_checks.py` (+ opt-in LLM-judge) | NIST MEASURE |

## 7. Cost & Budget Controls
| Control | Evidence | Satisfies |
|---|---|---|
| Per-run call caps | `MAX_CHUNKS_PER_DOC` (1000 in production), per-run LLM/embedding limits (`aiplatform.settings`) | Operational risk |
| Low-cost serverless footprint | Lambda, API Gateway, S3 and CloudFront of this app cost little and nothing runs on a schedule; the shared NAT gateway and RDS instance (about 96 USD per month for the whole account) are the real cost. There is no budget alert specific to this app; the account budget (50 USD) is shared and exceeded | Cost governance |

## 8. Known Gaps (documented)
| ID | Gap | Severity (today) | Trigger to fix |
|---|---|---|---|
| G1 | Consulting + engagement data in shared `db-v2`, not an isolated RDS | Critical (latent) | Before any **real** client engagement data is stored |
| G2 | No per-user application audit log | Medium | A second user, or real data processing |
| G3 | No WAF (cannot be attached to HTTP APIs); only default route throttling (10 req/s, burst 20) | Low | Exposure beyond the single admin |
| G7 | No bias assessment / incident-response / 72h breach process | Low | Moving toward production |
| G8 | Secrets are plaintext Lambda environment variables, not Secrets Manager | Medium | Before the repo or account is shared with others; before real data |
| G9 | No MFA on the Cognito admin, no CloudTrail trail, no CloudWatch alarms, no API access logs | Medium | Before real data or a second user |

Full analysis and coverage scoring: `../research/compliance_mapping.md`.

---

## Coverage Summary

| Framework | Coverage (implemented) |
|---|---|
| NIST AI RMF | 80 % (16 of 20) |
| GDPR / Swiss DSG | 72 % (13 of 18) |
| AWS Well-Architected (Security) | 63 % (9.5 of 15) |

Scoring: fully met = 1, partial = 0.5, missing = 0, divided by the requirements assessed (tables in
`../research/compliance_mapping.md`). These are self-assessment figures, not an audit or certification.
Corrected on 2026-09-26: the earlier 78 / 64 / 67 % were the values before the documents existed, and the
credentials control moved from done to partial (plaintext environment variables).

**Posture:** Demo-Ready ✅ · Customer-Ready 🟡 (workflow demo only, no real client data) ·
Production-Ready ❌ (close G1 → G2 → G3 first). Controls are appropriate for a private single-admin
portfolio demo that produces review drafts, never professional deliverables.
