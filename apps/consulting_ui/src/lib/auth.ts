// Single-admin Cognito browser auth (no SDK) — USER_PASSWORD_AUTH via fetch, token in
// localStorage, expiry-aware. Works with static export. Auth is ENABLED only when a Cognito
// client id is configured at build time; locally (no env) the app runs without auth, as before.

const REGION = process.env.NEXT_PUBLIC_CONSULTING_COGNITO_REGION ?? "eu-central-1";
const CLIENT_ID = process.env.NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID ?? "";
const COGNITO_URL = `https://cognito-idp.${REGION}.amazonaws.com/`;

const TOKEN_KEY = "consulting_id_token";
const EXPIRY_KEY = "consulting_token_expiry";
const EMAIL_KEY = "consulting_email";

/** True only in a deployed build where a Cognito client id was inlined. */
export const AUTH_ENABLED = CLIENT_ID !== "";

export interface Auth {
  idToken: string;
  email: string;
  expiresAt: number;
}

export async function login(email: string, password: string): Promise<Auth> {
  const res = await fetch(COGNITO_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    },
    body: JSON.stringify({
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: CLIENT_ID,
      AuthParameters: { USERNAME: email, PASSWORD: password },
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message ?? `Login failed (${res.status})`);
  }
  const data = await res.json();
  const idToken: string = data.AuthenticationResult.IdToken;
  const expiresAt = Date.now() + (data.AuthenticationResult.ExpiresIn ?? 3600) * 1000;
  localStorage.setItem(TOKEN_KEY, idToken);
  localStorage.setItem(EXPIRY_KEY, String(expiresAt));
  localStorage.setItem(EMAIL_KEY, email);
  return { idToken, email, expiresAt };
}

export function getAuth(): Auth | null {
  if (typeof window === "undefined") return null;
  const idToken = localStorage.getItem(TOKEN_KEY);
  const expiresAt = Number(localStorage.getItem(EXPIRY_KEY) ?? 0);
  if (!idToken || Date.now() >= expiresAt) return null;
  return { idToken, email: localStorage.getItem(EMAIL_KEY) ?? "", expiresAt };
}

export function getToken(): string | null {
  return getAuth()?.idToken ?? null;
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRY_KEY);
  localStorage.removeItem(EMAIL_KEY);
}
