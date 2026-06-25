# Deploying the AI Consulting Accelerator (Phase 1)

Backend = Lambda container behind an API Gateway HTTP API (Cognito JWT authorizer),
running inside the VPC so it can reach the private `ai-platform-db-v2`. Frontend =
Next.js static export on S3 + CloudFront. Auth = the consulting Cognito demo pool.

All scripts are **idempotent** — safe to re-run.

## Prerequisites

- Docker running; AWS CLI authenticated (`aws sts get-caller-identity`); region `eu-central-1`.
- Sibling repo present at `../ai-platform-project-v1` (provides `aiplatform`).
- VPC config: copy the platform's so the Lambda lands in subnets that can reach db-v2:
  ```bash
  mkdir -p infra && cp ../ai-platform-project-v1/infra/vpc_config.json infra/
  ```

## 1. Cognito demo pool

```bash
uv run python scripts/setup_consulting_cognito.py --demo-user demo@bridging-data.com --demo-password 'Demo1234!'
```
Note the printed **User Pool ID** and **App Client ID**.

## 2. Deploy the API (Lambda + API Gateway + JWT authorizer, in VPC)

Set production env vars (the prod db-v2 URL — NOT localhost), then deploy:

```bash
export DATABASE_URL='postgresql+asyncpg://USER:PASS@ai-platform-db-v2....rds.amazonaws.com:5432/postgres?ssl=require'
export ALEMBIC_DATABASE_URL='postgresql://USER:PASS@ai-platform-db-v2....rds.amazonaws.com:5432/postgres?sslmode=require'
export OPENAI_API_KEY='sk-...'
export CONSULTING_COGNITO_USER_POOL_ID='eu-central-1_xxxx'
export CONSULTING_COGNITO_CLIENT_ID='xxxx'

# Validate the image build locally first (no AWS):
uv run python scripts/deploy.py --build-only

# Full deploy:
uv run python scripts/deploy.py
```
Prints the **API endpoint**. Routes: `/health` + docs are public; `/api/v1/*` require a JWT.

## 3. Populate the production DB (one-off, runs inside the VPC)

The 23 frameworks live only locally until this runs. It ingests the PDFs baked into
the Lambda image directly into db-v2:

```bash
aws lambda invoke --function-name ai-consulting-api \
  --payload '{"action":"ingest"}' --cli-binary-format raw-in-base64-out \
  /dev/stdout --region eu-central-1
```
Expect `{"status":"ok","files":23}`. (~$2–5 of embeddings, one time.)

## 4. Deploy the frontend (S3 + CloudFront)

Build-time config inlines the API endpoint + Cognito client id:

```bash
export NEXT_PUBLIC_API_URL='https://<api-id>.execute-api.eu-central-1.amazonaws.com'
export NEXT_PUBLIC_CONSULTING_COGNITO_REGION='eu-central-1'
export NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID='xxxx'
uv run python scripts/deploy_frontend.py
```
Prints the **CloudFront URL** (first propagation ~10–15 min).

## 5. Allow the frontend origin in API CORS

Re-deploy the API with the CloudFront (or custom domain) origin:

```bash
uv run python scripts/deploy.py --frontend-origin https://<cloudfront-domain>
```

## 6. (Optional) Custom domain

Point `consulting.bridging-data.com` at the CloudFront distribution (Route 53 alias +
ACM cert in us-east-1). It is already in the API's CORS allow-list.

---

## Verify

- `curl https://<api-endpoint>/health` → `{"status":"ok","app":"consulting"}`
- Open the CloudFront URL → redirected to `/login` → sign in with the demo user →
  ask a question / structure an artifact.
- Unauthenticated `POST /api/v1/query` → `401` (JWT authorizer).

## Notes

- The Lambda image bakes `data/` (~40 MB of PDFs) so the one-off ingestion can run
  in-VPC. This is only needed for step 3; it does not affect request latency.
- API-side JWT verification is enforced by the API Gateway authorizer (not in app
  code). Locally the app runs without auth.
