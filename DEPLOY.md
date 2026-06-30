# Deploying the AI Consulting Accelerator (private, single-admin)

A **private** demo: one Cognito admin user logs in; there is no public sign-up. Architecture:

- **Backend:** Lambda **container** behind an API Gateway **HTTP API**, inside the VPC so it can
  reach the private `ai-platform-db-v2`. Routes: `GET /health` (public), `OPTIONS /{proxy+}`
  (no auth — CORS preflight), `$default` (Cognito **JWT authorizer** — everything else needs a token).
- **CORS is owned by the app** (Starlette `CORSMiddleware`, allow-list in `main.py`). API Gateway has
  **no** `CorsConfiguration` (two sources would double the headers and browsers reject that).
- **Frontend:** Next.js static export on S3 + CloudFront, custom domain via Route 53.
- **Auth in the UI activates only when Cognito is configured at build time** — locally the app runs
  without auth.

All scripts are idempotent — safe to re-run. They create **billable** AWS resources.

### Current deployment (eu-central-1, account <AWS_ACCOUNT_ID>)

| | |
|---|---|
| UI | https://consulting.bridging-data.com (also https://<CLOUDFRONT_DOMAIN>) |
| API | https://<API_ID>.execute-api.eu-central-1.amazonaws.com |
| Cognito | pool `<COGNITO_USER_POOL_ID>`, client `<COGNITO_CLIENT_ID>`, admin `<OWNER_EMAIL>` |
| CloudFront / S3 | dist `<CLOUDFRONT_DISTRIBUTION_ID>`, bucket `ai-consulting-ui` |
| Route 53 zone | `bridging-data.com` `<HOSTED_ZONE_ID>`; ACM `*.bridging-data.com` (us-east-1) |
| DB content | `consulting` 23/26 frameworks, `skills` 66, `projects` 4 (3 collide on global hash) |

---

## Prerequisites

- Docker running; AWS CLI authenticated (`aws sts get-caller-identity`); region `eu-central-1`.
- Sibling repo at `../ai-platform-project-v1` (provides `aiplatform` + the VPC config).
- VPC config (Lambda lands in subnets that can reach db-v2):
  ```bash
  mkdir -p infra && cp ../ai-platform-project-v1/infra/vpc_config.json infra/
  ```

## 0. Secrets — `infra/deploy.env` (gitignored, never committed)

```bash
export CONSULTING_ADMIN_EMAIL='you@example.com'
export CONSULTING_ADMIN_PASSWORD='…'          # >=8 chars, upper+lower+number (no symbol required)
export DATABASE_URL='postgresql+asyncpg://USER:PASS@ai-platform-db-v2.…rds.amazonaws.com:5432/postgres?ssl=require'
export ALEMBIC_DATABASE_URL='postgresql://USER:PASS@ai-platform-db-v2.…rds.amazonaws.com:5432/postgres?sslmode=require'
export OPENAI_API_KEY='sk-…'
# filled in after step 1:
export CONSULTING_COGNITO_USER_POOL_ID='eu-central-1_…'
export CONSULTING_COGNITO_CLIENT_ID='…'
```
The prod db-v2 URLs live in `../ai-platform-project-v1/.env`. `source infra/deploy.env` before each step.

## 1. Cognito — single admin user

```bash
set -a && source infra/deploy.env && set +a
uv run python scripts/setup_consulting_cognito.py \
  --demo-user "$CONSULTING_ADMIN_EMAIL" --demo-password "$CONSULTING_ADMIN_PASSWORD"
```
No self-registration (`AllowAdminCreateUserOnly`). Copy the printed **User Pool ID** + **Client ID**
into `infra/deploy.env`.

## 2. Deploy the API (Lambda + API Gateway, in VPC)

```bash
set -a && source infra/deploy.env && set +a
uv run python scripts/deploy.py --build-only          # validate the image (no AWS)
uv run python scripts/deploy.py --frontend-origin https://<CLOUDFRONT_DOMAIN>
```
Bakes `data/` (frameworks) **and** the Organizational Memory (toolkit skills + project READMEs under
`data/_memory/`). Prints the **API endpoint**. `--frontend-origin` adds the CloudFront URL to the
app's CORS allow-list (the custom domain is already in `_PRODUCTION_ORIGINS`).

`curl <api>/health` → `{"status":"ok","app":"consulting"}`; unauth `POST …/query` → `401`.

## 3. Populate the production DB (one-off, runs in-VPC)

Raise the limits first (ingest needs more than the 120s/1024MB serving defaults; **account max is 3008MB**):
```bash
FN=ai-consulting-api; R=eu-central-1
aws lambda update-function-configuration --function-name $FN --timeout 600 --memory-size 3008 --region $R
aws lambda wait function-updated --function-name $FN --region $R
```

**Frameworks — per file** (a single oversized PDF would otherwise block the bulk run, and exceed the
limits; per-file isolates each so the good ones commit and the oversized ones simply time out and are
skipped). Ingest is idempotent (SHA-256 dedup), so re-running only fills gaps:
```bash
for i in $(seq 0 25); do
  AWS_MAX_ATTEMPTS=1 aws lambda invoke --function-name $FN \
    --payload "{\"action\":\"ingest\",\"index\":$i}" --cli-binary-format raw-in-base64-out \
    --cli-read-timeout 650 --region $R /tmp/idx_$i.json
  echo "idx $i -> $(cat /tmp/idx_$i.json)"
done
```

**Organizational Memory** (skills + projects), then **check counts**:
```bash
aws lambda invoke --function-name $FN --payload '{"action":"ingest_memory"}' \
  --cli-binary-format raw-in-base64-out --cli-read-timeout 400 --region $R /tmp/mem.json
aws lambda invoke --function-name $FN --payload '{"action":"status"}' \
  --cli-binary-format raw-in-base64-out --region $R /tmp/status.json && cat /tmp/status.json
```

Reset the serving config when done (API Gateway caps web requests at 30s anyway):
```bash
aws lambda update-function-configuration --function-name $FN --timeout 120 --memory-size 1024 --region $R
```

## 4. Frontend (S3 + CloudFront)

```bash
export NEXT_PUBLIC_API_URL='https://<api-id>.execute-api.eu-central-1.amazonaws.com'
export NEXT_PUBLIC_CONSULTING_COGNITO_REGION='eu-central-1'
export NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID="$CONSULTING_COGNITO_CLIENT_ID"
uv run python scripts/deploy_frontend.py        # prints the CloudFront URL
```
Re-deploys invalidate with: `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`.

## 5. Custom domain (consulting.bridging-data.com)

Reuses the existing wildcard cert `*.bridging-data.com` (us-east-1) — no new cert needed. Add the
alias + cert to the distribution and a Route 53 alias record:
```python
import boto3
cf = boto3.client("cloudfront"); r53 = boto3.client("route53")
DIST="<CLOUDFRONT_DISTRIBUTION_ID>"; DOMAIN="consulting.bridging-data.com"; CFDNS="<CLOUDFRONT_DOMAIN>"
CERT="arn:aws:acm:us-east-1:<AWS_ACCOUNT_ID>:certificate/<ACM_CERT_ID>"; ZONE="<HOSTED_ZONE_ID>"
c = cf.get_distribution_config(Id=DIST); cfg, etag = c["DistributionConfig"], c["ETag"]
cfg["Aliases"] = {"Quantity": 1, "Items": [DOMAIN]}
cfg["ViewerCertificate"] = {"ACMCertificateArn": CERT, "SSLSupportMethod": "sni-only", "MinimumProtocolVersion": "TLSv1.2_2021"}
cf.update_distribution(Id=DIST, DistributionConfig=cfg, IfMatch=etag)
r53.change_resource_record_sets(HostedZoneId=ZONE, ChangeBatch={"Changes": [
  {"Action": "UPSERT", "ResourceRecordSet": {"Name": DOMAIN, "Type": t,
    "AliasTarget": {"HostedZoneId": "Z2FDTNDATAQYW2", "DNSName": CFDNS, "EvaluateTargetHealth": False}}}
  for t in ("A", "AAAA")]})
```
`Z2FDTNDATAQYW2` is the fixed hosted-zone id for all CloudFront distributions. Allow ~5–15 min for the
distribution to redeploy before HTTPS serves.

---

## Verify

- `curl https://<api>/health` → ok; unauth `POST …/query` → `401`.
- **Browser CORS** (the part that bit us — Python clients skip preflight): preflight must be 2xx with a
  single allow-origin, not 401:
  ```bash
  curl -i -X OPTIONS "<api>/api/v1/consulting/query" \
    -H "Origin: https://consulting.bridging-data.com" \
    -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: authorization,content-type"
  # -> HTTP 200, one access-control-allow-origin, no www-authenticate
  ```
- Open https://consulting.bridging-data.com → `/login` → sign in → Q&A, a structuring skill, and an
  engagement (create → conclude → generate knowledge/patterns → export) all work.

## Notes / gotchas (learned the hard way)

- **Warm-container asyncio.** Lambda reuses containers; the global async engine + `asyncio.run()` cause
  `got Future attached to a different loop`, and `asyncio.run()` leaves no current loop so the next
  Mangum (API) request 500s in `get_event_loop()`. `lambda_handler` handles both: `_with_fresh_pool`
  (dispose the pool) + `_run_action` (dedicated loop, then restore a fresh one). Don't reintroduce a
  bare `asyncio.run()` there.
- **Long ingests.** Use async invoke (`--invocation-type Event`) for long runs and poll `{"action":"status"}`;
  set `AWS_MAX_ATTEMPTS=1` (botocore retries re-fire the invoke on read-timeout).
- **Oversized PDFs.** `aws_well_architected`, `requirements_engineering_management` (74 MB), `uml_modellierung_v4`
  exceed 600s/3008MB and are skipped — acceptable for the demo. To ingest them: raise the limits if the
  account allows, or split them first (see the "3 large frameworks" follow-up).
- **Engagement DB** falls back to `DATABASE_URL` (shared db-v2) when `CONSULTING_ENGAGEMENT_DB_URL` is
  unset — fine for a single-admin demo with no real client data; use an isolated DB before any real
  client engagements. The engagement schema bootstrap needs a psycopg2 DSN (`sslmode=`, not `ssl=`).
- **Shared db-v2:** `documents_content_hash_key` is globally unique, so a README/PDF already indexed
  under another `app_name` is skipped (3 of 7 projects collide with platform copies).
