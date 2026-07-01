# Security Controls — Evidence Map

**System:** AI Consulting Accelerator — private single-admin demo
**Last updated:** July 2026
**Companion to:** `../research/compliance_mapping.md` (full framework assessment)

Each control below maps an implemented measure to the framework requirement it satisfies, with
concrete evidence. Known gaps are listed honestly in §8.

---

## 1. Authentication & Access Control
| Control | Evidence | Satisfies |
|---|---|---|
| Single-admin identity, no self-signup | Cognito pool `<COGNITO_USER_POOL_ID>`, `AllowAdminCreateUserOnly` (`scripts/setup_consulting_cognito.py`) | GDPR Art.32, WA IAM |
| Auth enforced at the edge | API Gateway JWT authorizer on `$default`; only `GET /health` + CORS-preflight `OPTIONS` public (`scripts/deploy.py`) | NIST GOVERN, WA IAM |
| Least-privilege compute role | `ai-consulting-lambda-role` (basic + VPC execution only) | WA IAM |
| No hardcoded credentials | Secrets injected as Lambda env; `.env` + `infra/deploy.env` gitignored (`.gitignore`) | WA IAM, Art.32 |

## 2. Data Isolation
| Control | Evidence | Satisfies |
|---|---|---|
| Application scoping | `app_name="consulting"` / `"skills"` / `"projects"` on every row | Purpose limitation (Art.5) |
| Network isolation | RDS `ai-platform-db-v2` `PubliclyAccessible=false`, in `<VPC_ID>` | WA Infrastructure Protection |
| Dedicated engagement engine (code path) | `CONSULTING_ENGAGEMENT_DB_URL` via a separate SQLAlchemy engine (`storage/engagement_db.py`) | Confidentiality (Art.32) |
| ⚠️ Physical DB isolation | **Not yet** — consulting + engagement data share `db-v2` (see gap G1) | — |

## 3. Data Encryption
| Control | Evidence | Satisfies |
|---|---|---|
| Encryption at rest | RDS `StorageEncrypted=true` (verified via AWS CLI) | Art.32, WA Data Protection |
| Encryption in transit | HTTPS (API Gateway + CloudFront); RDS `ssl/sslmode=require` | Art.32, WA Data Protection |
| TLS-only frontend | CloudFront with ACM cert; custom domain `consulting.bridging-data.com` | Art.32 |

## 4. Audit Logging
| Control | Evidence | Satisfies |
|---|---|---|
| Infrastructure logs | CloudWatch logs for `ai-consulting-api` Lambda | WA Detection |
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
| Per-run call caps | `MAX_CHUNKS_PER_DOC`, per-run LLM/embedding limits (`aiplatform.settings`) | Operational risk |
| Low-cost serverless footprint | Lambda + serverless; target < $5/month; user-triggered only (no schedulers) | Cost governance |

## 8. Known Gaps (documented)
| ID | Gap | Severity (today) | Trigger to fix |
|---|---|---|---|
| G1 | Consulting + engagement data in shared `db-v2`, not an isolated RDS | Critical (latent) | Before any **real** client engagement data is stored |
| G2 | No per-user application audit log | Medium | A second user, or real data processing |
| G3 | No WAF / rate limiting on the API | Medium | Exposure beyond the single admin |
| G7 | No bias assessment / incident-response / 72h breach process | Low | Moving toward production |

Full analysis and coverage scoring: `../research/compliance_mapping.md`.

---

## Coverage Summary

| Framework | Coverage (implemented) |
|---|---|
| NIST AI RMF | 78 % |
| GDPR / Swiss DSG | 64 % |
| AWS Well-Architected (Security) | 67 % |

**Posture:** Demo-Ready ✅ · Customer-Ready 🟡 (workflow demo only, no real client data) ·
Production-Ready ❌ (close G1 → G2 → G3 first). Controls are appropriate for a private single-admin
portfolio demo that produces review drafts, never professional deliverables.
