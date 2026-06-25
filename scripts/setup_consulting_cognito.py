#!/usr/bin/env python3
"""
Create the Cognito User Pool + app client for the consulting demo.

Admin-created users only — NO public self-registration (controls access and cost).
Run once:
    uv run python scripts/setup_consulting_cognito.py

Optionally create a demo user in the same run (sets a permanent password, so the
first login is a plain USER_PASSWORD_AUTH with no NEW_PASSWORD_REQUIRED challenge):
    uv run python scripts/setup_consulting_cognito.py --demo-user demo@example.com --demo-password 'Demo1234'

After running, copy the printed IDs into apps/consulting_ui/.env.local:
    NEXT_PUBLIC_CONSULTING_COGNITO_REGION=eu-central-1
    NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID=<printed client id>
"""

import argparse

import boto3

REGION = "eu-central-1"
POOL_NAME = "ai-consulting-demo"
CLIENT_NAME = "consulting-ui"


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the consulting Cognito user pool.")
    parser.add_argument("--demo-user", help="Email of a demo user to create (admin-created).")
    parser.add_argument("--demo-password", help="Permanent password for the demo user.")
    args = parser.parse_args()

    cognito = boto3.client("cognito-idp", region_name=REGION)

    # 1. User pool — admin-created users only, no self sign-up
    pools = cognito.list_user_pools(MaxResults=60)["UserPools"]
    existing = next((p for p in pools if p["Name"] == POOL_NAME), None)
    if existing:
        pool_id = existing["Id"]
        print(f"User pool already exists: {pool_id}")
    else:
        resp = cognito.create_user_pool(
            PoolName=POOL_NAME,
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": False,
                }
            },
            UsernameAttributes=["email"],
            UsernameConfiguration={"CaseSensitive": False},
            # No self-registration — only admins create users.
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
        )
        pool_id = resp["UserPool"]["Id"]
        print(f"Created user pool: {pool_id}")

    # 2. App client — public (no secret), browser-based USER_PASSWORD_AUTH
    clients = cognito.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)["UserPoolClients"]
    existing_client = next((c for c in clients if c["ClientName"] == CLIENT_NAME), None)
    if existing_client:
        client_id = existing_client["ClientId"]
        print(f"App client already exists: {client_id}")
    else:
        resp = cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=CLIENT_NAME,
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = resp["UserPoolClient"]["ClientId"]
        print(f"Created app client: {client_id}")

    # 3. Optional: create a demo user with a permanent password
    if args.demo_user and args.demo_password:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=args.demo_user,
            UserAttributes=[
                {"Name": "email", "Value": args.demo_user},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",
        )
        cognito.admin_set_user_password(
            UserPoolId=pool_id,
            Username=args.demo_user,
            Password=args.demo_password,
            Permanent=True,
        )
        print(f"Created demo user: {args.demo_user}")
    elif args.demo_user or args.demo_password:
        print("Note: provide BOTH --demo-user and --demo-password to create a demo user.")

    print("\n--- Add to apps/consulting_ui/.env.local ---")
    print(f"NEXT_PUBLIC_CONSULTING_COGNITO_REGION={REGION}")
    print(f"NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID={client_id}")
    print("\n--- Create more demo users later with: ---")
    print(f'  aws cognito-idp admin-create-user --user-pool-id {pool_id} --username USER_EMAIL --message-action SUPPRESS --region {REGION}')
    print(f'  aws cognito-idp admin-set-user-password --user-pool-id {pool_id} --username USER_EMAIL --password PASSWORD --permanent --region {REGION}')


if __name__ == "__main__":
    main()
