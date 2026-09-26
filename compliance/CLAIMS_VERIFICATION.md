# Claims Verification Log

**Date of check:** 2026-09-26  
**Method:** every statement in `compliance/` and `research/compliance_mapping.md` that asserts a technical control
or a fact about the deployment was compared with the code in this repository and with the live AWS account
(`eu-central-1`) using read-only calls (API Gateway, Lambda configuration, IAM, Cognito, RDS, CloudFront, S3,
CloudWatch). Secret values were never printed. This is a self-check by the owner, not an audit or a certification.

**Verdicts:** ✅ verified as stated · ✏️ was wrong or imprecise, text corrected · ❔ could not be verified ·
➖ policy or intent statement, not a technical claim

Most statements were accurate. The discrepancies below were corrected in the documents instead of adjusting the
deployment to the text, except the two live changes listed at the end.

---

## SECURITY_CONTROLS.md and compliance_mapping.md

| # | Claim | Actual state (2026-09-26) | Verdict |
|---|---|---|---|
| 1 | Single admin, no self-signup (Cognito) | One confirmed user, `AllowAdminCreateUserOnly=true`, no groups. MFA is off (not stated before) | ✅ / ✏️ |
| 2 | JWT authorizer on `$default`; only `GET /health` and the CORS-preflight `OPTIONS` are public | Exactly these three routes exist; `$default` has the JWT authorizer, `/health` and `OPTIONS /{proxy+}` have none | ✅ |
| 3 | (not stated) who may call the API | Any valid token of the pool is accepted, there is no group check. Safe only because the pool has one user and no self-signup; now stated | ✏️ |
| 4 | Least-privilege compute role: basic + VPC execution only | `ai-consulting-lambda-role` has exactly the two AWS-managed policies and no inline policy | ✅ |
| 5 | No hardcoded credentials; secrets injected as Lambda env, `.env` and `infra/deploy.env` gitignored | Not in git: all 69 commits on all branches scanned, no key, no private key, no password; `.env` never tracked. But `OPENAI_API_KEY`, `DATABASE_URL` and `ALEMBIC_DATABASE_URL` are plaintext Lambda environment variables (Secrets Manager is not used). Control downgraded to partial, new gap G8 | ✏️ |
| 6 | `app_name` scoping on every row | On every `documents` row; the `consulting_engagements` table has no `app_name` column | ✏️ |
| 7 | RDS `PubliclyAccessible=false`, in the VPC, encrypted | `ai-platform-db-v2`: not public, `StorageEncrypted=true`, only the Lambda security group may connect | ✅ |
| 8 | Dedicated engagement engine via `CONSULTING_ENGAGEMENT_DB_URL` | The code path exists. The variable is **not set in production**, so the engine uses `DATABASE_URL` = shared `db-v2` (gap G1 is real and current) | ✅ / ✏️ |
| 9 | README: engagement DB is "an isolated DB in prod" (three places) | Wrong, see #8. README and comments corrected; ROPA and SECURITY_CONTROLS had it right | ✏️ |
| 10 | RDS `ssl/sslmode=require` | Both connection URLs request SSL and the default PostgreSQL 16 parameter group has `rds.force_ssl=1`; the enforcement source is now named | ✏️ |
| 11 | TLS-only frontend (CloudFront + ACM) | CloudFront redirects to HTTPS with TLS 1.2 minimum. The S3 origin is a public website endpoint (public `GetObject` bucket policy), so the static UI files are also reachable over plain HTTP directly from S3. They contain no secrets | ✏️ |
| 12 | CloudWatch logs for the Lambda | Log group exists; retention was unlimited, now 30 days. No CloudWatch alarms, no API access logging, no CloudTrail trail | ✏️ |
| 13 | No per-user audit trail (G2) | Correct, no audit code | ✅ |
| 14 | Right to erasure: engagement delete cascades | `EngagementService.delete()` and the DELETE route exist | ✅ |
| 15 | SHA-256 `content_hash` unique | Column is unique (shared model) | ✅ |
| 16 | 14 named skills (ROPA, MODEL_CARD) | The registry has 17; README already said 17 | ✏️ |
| 17 | `SourceReference{source_uri, score}` per answer | The schema has `chunk_id`, `source_uri`, `score`, `excerpt`, `category`, `language`; the statement was a subset | ✅ |
| 18 | Quality eval harness (`eval.py`, `eval_checks.py`) | Files and tests exist (79 unit tests pass) | ✅ |
| 19 | Per-run caps: `MAX_CHUNKS_PER_DOC` and LLM/embedding limits | `MAX_CHUNKS_PER_DOC=1000` deployed; the embedder raises `CostLimitExceeded`, handled in the routes | ✅ |
| 20 | Cost target below 5 USD per month, no schedulers | No EventBridge rules exist for this app. The app's own cost is small, but it shares the NAT gateway and the RDS instance with the platform (about 96 USD per month for the whole account); no app-specific budget alert | ✏️ |
| 21 | Gap G3: no WAF / rate limiting | WAF still absent (not available for HTTP APIs). Default route throttling of 10 req/s, burst 20 was added on 2026-09-26 | ✏️ |
| 22 | Gaps: no GuardDuty, no CloudTrail alerts, no incident-response or breach docs | Correct; also no trail and no alarms | ✅ |
| 23 | Coverage 78 % (15.5/20), 64 % (11.5/18), 67 % (10/15) | Arithmetic checked against the tables: correct | ✅ |
| 24 | Coverage "after docs": GDPR 75 % (13.5/18), AWS 70 % (10.5/15) | The tables support 13/18 = 72 % for GDPR and no change for AWS. With the credentials control downgraded (#5) AWS is 9.5/15 = 63 %. Corrected in both documents | ✏️ |

## MODEL_CARD.md

| # | Claim | Actual state | Verdict |
|---|---|---|---|
| 25 | `gpt-4o-mini`, `text-embedding-3-small` (1536), `LLM_PROVIDER=openai` | Lambda environment matches | ✅ |
| 26 | 23 of 26 PDFs indexed; three oversized ones skipped | 26 PDFs in `data/`; the live database holds 23 `consulting` documents | ✅ |
| 27 | Skills: 14 | 17 | ✏️ |
| 28 | Monitoring: CloudWatch, caps, cost target below 5 USD | See #12 and #20 | ✏️ |
| 29 | API key from the Lambda environment | True, but plaintext in the function configuration; now stated | ✏️ |
| 30 | Provider swappable (`LLM_PROVIDER=openai\|anthropic`) | Setting exists; the Anthropic path was not exercised | ❔ |

## ROPA.md

| # | Claim | Actual state | Verdict |
|---|---|---|---|
| 31 | Engagements stored in the shared `db-v2`, not isolated (G1) | Confirmed against the live Lambda configuration | ✅ |
| 32 | Framework Q&A: queries not persisted | The query and structure flows contain no database writes | ✅ |
| 33 | Organizational memory in `db-v2` (`skills`, `projects`) | 66 and 4 documents in the live database | ✅ |
| 34 | Sub-processors: OpenAI, AWS with six services | Also Route 53, ECR and CloudWatch; CloudFront and Route 53 are global, the certificate is in us-east-1. Completed | ✏️ |
| 35 | (missing) processing of the administrator's account data | Cognito holds the admin e-mail address; added as processing activity 5 | ✏️ |
| 36 | Data subject rights: access, erasure, portability, rectification | Engagement list/detail, export (md/docx/pdf) and delete routes exist | ✅ |
| 37 | OpenAI does not train on API data | Statement about a third party | ❔ |

## README.md and DEPLOY.md

| # | Claim | Actual state | Verdict |
|---|---|---|---|
| 38 | 66 skills and 7 projects live | 66 skills and 4 projects (three READMEs collide on the global hash with platform copies, as DEPLOY.md already said) | ✏️ |
| 39 | Serve the Lambda with 1024 MB | With 1024 MB the init phase took 13.5 s and hit AWS's 10 s init limit, so the first request after idle returned HTTP 500. At 2048 MB a cold start takes about 4 s | ✏️ |

## Repository checks (secrets and identifiers)

| Check | Result |
|---|---|
| All commits, all branches (69 commits, `main` and `phase-1-setup`): API keys, private keys, tokens, passwords in connection strings | None. The connection strings in `DEPLOY.md` and `.env.example` are placeholders (`USER:PASS`) |
| `.env`, `infra/deploy.env`, `infra/vpc_config.json` in any commit | Never tracked |
| Identifiers in the current tree | Account ID, API ID, Cognito pool and client, CloudFront distribution and domain, hosted zone, ACM ARN, VPC ID and the owner's private e-mail address were in five documents (`DEPLOY.md`, three compliance documents, `compliance_mapping.md`); replaced with placeholders. History keeps the old values (identifiers, not secrets) |
| Local paths | Two scripts hard-coded `C:\Users\lucia\...`; they now use `PROJECTS_ROOT` / `SKILLS_DIR` or the sibling-folder layout |
| Third-party material | The repository tracks 26 framework PDFs and some course files (181 MB) whose redistribution rights are not established; under review by the owner |

## Live changes made during this check

- API Gateway default route throttling: 10 requests/s, burst 20 (was unlimited).
- Lambda memory 1024 → 2048 MB to fix the cold-start failure (#39).
- CloudWatch log retention 30 days (done account-wide before).

## Still open

G1 isolated engagement database, G2 audit log, G3 WAF, G7 bias/incident/breach documents, G8 secrets in Secrets
Manager, G9 MFA, CloudTrail trail and alarms (see `SECURITY_CONTROLS.md` section 8).
