#!/usr/bin/env python3
"""
Build and deploy the Next.js demo UI as a static site: S3 (static website hosting)
behind a CloudFront distribution (HTTPS + CDN).

Re-running is safe: it reuses the existing bucket / distribution and re-uploads.

The UI is configured at BUILD time via env vars (NEXT_PUBLIC_* are inlined), so the
deployed API endpoint and Cognito client id must be set before building:

    export NEXT_PUBLIC_API_URL=https://<api-id>.execute-api.eu-central-1.amazonaws.com
    export NEXT_PUBLIC_CONSULTING_COGNITO_REGION=eu-central-1
    export NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID=<client id>
    uv run python scripts/deploy_frontend.py

Note: this uses a public-read S3 website bucket fronted by CloudFront — a common,
simple pattern for a public demo. Review before running; CloudFront/SPA routing
behaviour is not verifiable locally.
"""

import json
import mimetypes
import subprocess
import sys
import time
from pathlib import Path

import boto3

REGION = "eu-central-1"
BUCKET = "ai-consulting-ui"
UI_DIR = Path(__file__).resolve().parent.parent / "apps" / "consulting_ui"
OUT_DIR = UI_DIR / "out"


def build_ui() -> None:
    print("  [ui] npm run build (static export)")
    subprocess.run(["npm", "run", "build"], cwd=UI_DIR, check=True, shell=True)
    if not (OUT_DIR / "index.html").exists():
        sys.exit("ERROR: out/index.html not found — static export did not produce output.")


def ensure_bucket(s3) -> None:
    buckets = {b["Name"] for b in s3.list_buckets()["Buckets"]}
    if BUCKET not in buckets:
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        print(f"  [s3] created bucket {BUCKET}")
    s3.put_public_access_block(
        Bucket=BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": False, "IgnorePublicAcls": False,
            "BlockPublicPolicy": False, "RestrictPublicBuckets": False,
        },
    )
    s3.put_bucket_website(
        Bucket=BUCKET,
        WebsiteConfiguration={
            "IndexDocument": {"Suffix": "index.html"},
            "ErrorDocument": {"Key": "404.html"},
        },
    )
    s3.put_bucket_policy(
        Bucket=BUCKET,
        Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicReadForWebsite",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{BUCKET}/*",
            }],
        }),
    )
    print(f"  [s3] website hosting configured on {BUCKET}")


def upload(s3) -> None:
    files = [p for p in OUT_DIR.rglob("*") if p.is_file()]
    for path in files:
        key = str(path.relative_to(OUT_DIR)).replace("\\", "/")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        s3.upload_file(
            str(path), BUCKET, key,
            ExtraArgs={"ContentType": content_type},
        )
    print(f"  [s3] uploaded {len(files)} files")


def ensure_distribution(cf) -> tuple[str, str]:
    website_origin = f"{BUCKET}.s3-website.{REGION}.amazonaws.com"
    dists = cf.list_distributions().get("DistributionList", {}).get("Items", [])
    for d in dists:
        for origin in d["Origins"]["Items"]:
            if origin["DomainName"] == website_origin:
                print(f"  [cf] distribution exists: {d['Id']}")
                return d["Id"], d["DomainName"]

    resp = cf.create_distribution(
        DistributionConfig={
            "CallerReference": f"consulting-ui-{int(time.time())}",
            "Comment": "AI Consulting Accelerator demo UI",
            "Enabled": True,
            "DefaultRootObject": "index.html",
            "Origins": {
                "Quantity": 1,
                "Items": [{
                    "Id": "s3-website",
                    "DomainName": website_origin,
                    "CustomOriginConfig": {
                        "HTTPPort": 80, "HTTPSPort": 443,
                        "OriginProtocolPolicy": "http-only",
                    },
                }],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": "s3-website",
                "ViewerProtocolPolicy": "redirect-to-https",
                "Compress": True,
                # CachingOptimized managed policy
                "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
            },
        },
    )
    dist = resp["Distribution"]
    print(f"  [cf] created distribution: {dist['Id']}")
    return dist["Id"], dist["DomainName"]


def main() -> None:
    build_ui()
    s3 = boto3.client("s3", region_name=REGION)
    cf = boto3.client("cloudfront")

    ensure_bucket(s3)
    upload(s3)
    dist_id, domain = ensure_distribution(cf)

    print("\nFrontend deployed.")
    print(f"  CloudFront: https://{domain}")
    print("  (First deploy takes ~10-15 min to propagate.)")
    print("  Re-deploy: re-run this script; then invalidate the CDN cache:")
    print(f'    aws cloudfront create-invalidation --distribution-id {dist_id} --paths "/*"')
    print("\nRemember: add the CloudFront URL to the API CORS allow-list, e.g. redeploy the API with")
    print(f"  --frontend-origin https://{domain}")


if __name__ == "__main__":
    main()
