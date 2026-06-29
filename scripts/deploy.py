#!/usr/bin/env python3
"""
Deploy the consulting API as a Lambda container behind an API Gateway HTTP API
with a Cognito JWT authorizer, inside the VPC (so it can reach the private db-v2).

Re-running is safe: it updates the existing function / API instead of duplicating.

Prerequisites (one-time):
  * Docker running, AWS CLI authenticated, ECR access.
  * VPC config at infra/vpc_config.json (reuse the platform's: copy it from
    ../ai-platform-project-v1/infra/vpc_config.json — Lambda must sit in the same
    private subnets / security group that can reach ai-platform-db-v2).
  * Cognito pool created (scripts/setup_consulting_cognito.py).

Required environment variables when deploying (NOT --build-only):
  DATABASE_URL                       prod db-v2 asyncpg URL (must NOT be localhost)
  ALEMBIC_DATABASE_URL               prod db-v2 psycopg2 URL
  OPENAI_API_KEY                     OpenAI key
  CONSULTING_COGNITO_USER_POOL_ID    from setup_consulting_cognito.py
  CONSULTING_COGNITO_CLIENT_ID       from setup_consulting_cognito.py

Usage:
  uv run python scripts/deploy.py --build-only      # stage + docker build, no AWS
  uv run python scripts/deploy.py                    # full deploy
  uv run python scripts/deploy.py --frontend-origin https://consulting.bridging-data.com
"""

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import boto3

REGION = "eu-central-1"
FUNCTION_NAME = "ai-consulting-api"
ECR_REPO_NAME = "ai-consulting-api"
ROLE_NAME = "ai-consulting-lambda-role"
API_NAME = "ai-consulting-api"
HANDLER = "apps.consulting_api.lambda_handler.handler"
IMAGE_TAG = "lambda"

REPO_ROOT = Path(__file__).resolve().parent.parent
AIPLATFORM_REPO = REPO_ROOT.parent / "ai-platform-project-v1"
BUILD_CONTEXT = REPO_ROOT / "build" / "lambda"

_BASIC_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
_VPC_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"

# Routes: /health and docs are public; the data endpoints require a valid JWT.
ROUTE_CONFIGS = [
    ("GET /health", False),
    ("POST /api/v1/query", True),
    ("POST /api/v1/structure", True),
    ("GET /api/v1/skills", True),
    ("GET /api/v1/sources", True),
    ("$default", False),  # /docs, /openapi.json, etc.
]


# ── Build context staging ─────────────────────────────────────────────────────

def stage_build_context() -> None:
    """Assemble build/lambda/ with the consulting app + the aiplatform source."""
    if not AIPLATFORM_REPO.is_dir():
        sys.exit(f"ERROR: sibling aiplatform repo not found at {AIPLATFORM_REPO}")

    if BUILD_CONTEXT.exists():
        shutil.rmtree(BUILD_CONTEXT)
    BUILD_CONTEXT.mkdir(parents=True)

    print(f"  [stage] build context -> {BUILD_CONTEXT}")
    for rel in ["apps", "scripts", "data"]:
        shutil.copytree(
            REPO_ROOT / rel,
            BUILD_CONTEXT / rel,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copytree(
        AIPLATFORM_REPO / "aiplatform",
        BUILD_CONTEXT / "aiplatform",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy(REPO_ROOT / "Dockerfile.lambda", BUILD_CONTEXT / "Dockerfile.lambda")

    _stage_org_memory(BUILD_CONTEXT / "data" / "_memory")
    _write_requirements(BUILD_CONTEXT / "requirements.lambda.txt")
    print("  [stage] done")


def _stage_org_memory(mem: Path) -> None:
    """Bake the Organizational Memory into the image so it can be ingested in-VPC after deploy:
    toolkit skills (preserving <category>/<name>/SKILL.md) and each project README as <slug>.md.
    Read from their real local paths at build time — nothing is committed to this repo."""
    from scripts.ingest_projects_local import PROJECTS, find_readme
    from scripts.ingest_skills import DEFAULT_SKILLS_DIR

    skills, projects = 0, 0
    if DEFAULT_SKILLS_DIR.is_dir():
        for skill_md in DEFAULT_SKILLS_DIR.rglob("SKILL.md"):
            dst = mem / "skills" / skill_md.relative_to(DEFAULT_SKILLS_DIR)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(skill_md, dst)
            skills += 1
    (mem / "projects").mkdir(parents=True, exist_ok=True)
    for path, slug, _label in PROJECTS:
        readme = find_readme(Path(path))
        if readme is not None:
            shutil.copy(readme, mem / "projects" / f"{slug}.md")
            projects += 1
    print(f"  [stage] org memory — {skills} skills, {projects} project READMEs")


def _write_requirements(target: Path) -> None:
    """Export third-party deps via uv, dropping the local ai-platform path dep."""
    out = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-project"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    kept: list[str] = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "-e ")):
            continue
        if "ai-platform" in stripped:  # provided as source, not a wheel
            continue
        # Keep only requirement specifiers (PyPI pins or direct URLs)
        if "==" in stripped or " @ " in stripped:
            kept.append(stripped)

    target.write_text("\n".join(kept) + "\n")
    print(f"  [stage] requirements.lambda.txt — {len(kept)} packages")


# ── Docker build + ECR push ───────────────────────────────────────────────────

def docker_build(image_uri: str) -> None:
    print(f"  [docker] building {image_uri}")
    subprocess.run(
        ["docker", "build", "-f", str(BUILD_CONTEXT / "Dockerfile.lambda"),
         "-t", image_uri, str(BUILD_CONTEXT)],
        check=True,
    )


def ensure_ecr_repo(ecr) -> str:
    try:
        repo = ecr.describe_repositories(repositoryNames=[ECR_REPO_NAME])["repositories"][0]
    except ecr.exceptions.RepositoryNotFoundException:
        repo = ecr.create_repository(repositoryName=ECR_REPO_NAME)["repository"]
        print(f"  [ecr] created repo {ECR_REPO_NAME}")
    return repo["repositoryUri"]


def ecr_login_and_push(ecr, image_uri: str) -> None:
    token = ecr.get_authorization_token()["authorizationData"][0]
    registry = token["proxyEndpoint"]
    import base64

    user, password = base64.b64decode(token["authorizationToken"]).decode().split(":", 1)
    subprocess.run(
        ["docker", "login", "--username", user, "--password-stdin", registry],
        input=password, text=True, check=True,
    )
    subprocess.run(["docker", "push", image_uri], check=True)
    print(f"  [ecr] pushed {image_uri}")


# ── IAM / Lambda / API Gateway ────────────────────────────────────────────────

def load_vpc_config() -> dict:
    path = REPO_ROOT / "infra" / "vpc_config.json"
    if not path.exists():
        sys.exit(
            "ERROR: infra/vpc_config.json missing. The Lambda must run in the VPC to "
            "reach the private db-v2. Copy it from ../ai-platform-project-v1/infra/."
        )
    return json.loads(path.read_text())


def create_or_get_role(iam) -> str:
    try:
        role = iam.get_role(RoleName=ROLE_NAME)
        print(f"  [iam] role '{ROLE_NAME}' exists")
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass
    assume = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow",
                       "Principal": {"Service": "lambda.amazonaws.com"},
                       "Action": "sts:AssumeRole"}],
    })
    role = iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=assume)
    for policy in [_BASIC_POLICY, _VPC_POLICY]:
        iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=policy)
    print(f"  [iam] role '{ROLE_NAME}' created — waiting 15s for propagation")
    time.sleep(15)
    return role["Role"]["Arn"]


def build_env_vars(frontend_origin: str | None) -> dict[str, str]:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or "localhost" in db_url or "127.0.0.1" in db_url:
        sys.exit("ERROR: set DATABASE_URL to the production db-v2 asyncpg URL (not localhost).")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        sys.exit("ERROR: OPENAI_API_KEY not set.")

    env = {
        "APP_ENV": "production",
        "DATABASE_URL": db_url,
        "ALEMBIC_DATABASE_URL": os.environ.get("ALEMBIC_DATABASE_URL", ""),
        "OPENAI_API_KEY": openai_key,
        "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", "openai"),
        "OPENAI_CHAT_MODEL": os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        "OPENAI_EMBEDDING_MODEL": os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "MAX_CHUNKS_PER_DOC": os.environ.get("MAX_CHUNKS_PER_DOC", "1000"),
    }
    if frontend_origin:
        # Appended to the API's production CORS allow-list (see main.py).
        env["CONSULTING_CORS_ORIGINS"] = frontend_origin
    return env


def create_or_update_lambda(lambda_client, role_arn: str, image_uri: str,
                            vpc: dict, frontend_origin: str | None) -> str:
    env_vars = {"Variables": build_env_vars(frontend_origin)}
    vpc_config = {
        "SubnetIds": [vpc["subnets"]["private-1a"], vpc["subnets"]["private-1b"]],
        "SecurityGroupIds": [vpc["security_groups"]["lambda"]],
    }
    try:
        existing = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        print(f"  [lambda] updating {FUNCTION_NAME}")
        lambda_client.update_function_code(FunctionName=FUNCTION_NAME, ImageUri=image_uri)
        lambda_client.get_waiter("function_updated").wait(FunctionName=FUNCTION_NAME)
        lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            ImageConfig={"Command": [HANDLER]},
            Environment=env_vars,
            Timeout=120,
            MemorySize=1024,
            VpcConfig=vpc_config,
        )
        return existing["Configuration"]["FunctionArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"  [lambda] creating {FUNCTION_NAME}")
        resp = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            PackageType="Image",
            Code={"ImageUri": image_uri},
            Role=role_arn,
            ImageConfig={"Command": [HANDLER]},
            Environment=env_vars,
            Timeout=120,
            MemorySize=1024,
            VpcConfig=vpc_config,
        )
        lambda_client.get_waiter("function_active").wait(FunctionName=FUNCTION_NAME)
        return resp["FunctionArn"]


def setup_api(apigw, lambda_client, fn_arn: str, account_id: str,
              pool_id: str, client_id: str, frontend_origin: str | None) -> str:
    issuer = f"https://cognito-idp.{REGION}.amazonaws.com/{pool_id}"
    origins = [o for o in [frontend_origin, "https://consulting.bridging-data.com",
                           "http://localhost:3000"] if o]

    apis = apigw.get_apis(MaxResults="100")["Items"]
    api = next((a for a in apis if a["Name"] == API_NAME), None)
    if api:
        api_id, endpoint = api["ApiId"], api["ApiEndpoint"]
        print(f"  [apigw] API exists: {api_id}")
    else:
        created = apigw.create_api(
            Name=API_NAME, ProtocolType="HTTP",
            CorsConfiguration={
                "AllowOrigins": origins,
                "AllowMethods": ["GET", "POST", "OPTIONS"],
                "AllowHeaders": ["Content-Type", "Authorization"],
                "MaxAge": 300,
            },
        )
        api_id, endpoint = created["ApiId"], created["ApiEndpoint"]
        print(f"  [apigw] created API: {api_id}")

    authorizers = apigw.get_authorizers(ApiId=api_id)["Items"]
    auth = next((a for a in authorizers if a["Name"] == "cognito-jwt"), None)
    if auth:
        auth_id = auth["AuthorizerId"]
    else:
        auth_id = apigw.create_authorizer(
            ApiId=api_id, Name="cognito-jwt", AuthorizerType="JWT",
            IdentitySource=["$request.header.Authorization"],
            JwtConfiguration={"Audience": [client_id], "Issuer": issuer},
        )["AuthorizerId"]
        print(f"  [apigw] JWT authorizer created: {auth_id}")

    integrations = apigw.get_integrations(ApiId=api_id)["Items"]
    integration = next((i for i in integrations if fn_arn in i.get("IntegrationUri", "")), None)
    if integration:
        integration_id = integration["IntegrationId"]
    else:
        integration_id = apigw.create_integration(
            ApiId=api_id, IntegrationType="AWS_PROXY",
            IntegrationUri=fn_arn, PayloadFormatVersion="2.0",
        )["IntegrationId"]
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME, StatementId="AllowAPIGatewayInvoke",
            Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{account_id}:{api_id}/*/*",
        )
        print(f"  [apigw] integration created: {integration_id}")

    existing_routes = {r["RouteKey"] for r in apigw.get_routes(ApiId=api_id)["Items"]}
    for route_key, require_auth in ROUTE_CONFIGS:
        if route_key in existing_routes:
            continue
        kwargs = {"ApiId": api_id, "RouteKey": route_key,
                  "Target": f"integrations/{integration_id}"}
        if require_auth:
            kwargs["AuthorizationType"] = "JWT"
            kwargs["AuthorizerId"] = auth_id
        else:
            kwargs["AuthorizationType"] = "NONE"
        apigw.create_route(**kwargs)
        print(f"  [apigw] route: {route_key} (auth={require_auth})")

    with contextlib.suppress(apigw.exceptions.ConflictException):
        apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    return endpoint


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy the consulting API.")
    parser.add_argument("--build-only", action="store_true",
                        help="Stage context + docker build only (no ECR/AWS).")
    parser.add_argument("--frontend-origin", help="Frontend origin to allow in CORS.")
    args = parser.parse_args()

    stage_build_context()

    if args.build_only:
        docker_build(f"{ECR_REPO_NAME}:{IMAGE_TAG}")
        print("\nBuild-only complete. Run a container locally to smoke-test the handler.")
        return

    pool_id = os.environ.get("CONSULTING_COGNITO_USER_POOL_ID")
    client_id = os.environ.get("CONSULTING_COGNITO_CLIENT_ID")
    if not pool_id or not client_id:
        sys.exit("ERROR: set CONSULTING_COGNITO_USER_POOL_ID and CONSULTING_COGNITO_CLIENT_ID.")

    sts = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    ecr = boto3.client("ecr", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)
    lambda_client = boto3.client("lambda", region_name=REGION)
    apigw = boto3.client("apigatewayv2", region_name=REGION)

    repo_uri = ensure_ecr_repo(ecr)
    image_uri = f"{repo_uri}:{IMAGE_TAG}"
    docker_build(image_uri)
    ecr_login_and_push(ecr, image_uri)

    vpc = load_vpc_config()
    role_arn = create_or_get_role(iam)
    fn_arn = create_or_update_lambda(lambda_client, role_arn, image_uri, vpc, args.frontend_origin)
    endpoint = setup_api(apigw, lambda_client, fn_arn, account_id, pool_id, client_id, args.frontend_origin)

    print(f"\nDeployed. API endpoint: {endpoint}")
    print("Next: populate the production DB (one-off, runs inside the VPC):")
    print(f'  aws lambda invoke --function-name {FUNCTION_NAME} --payload \'{{"action":"ingest"}}\' --cli-binary-format raw-in-base64-out /dev/stdout --region {REGION}')


if __name__ == "__main__":
    main()
