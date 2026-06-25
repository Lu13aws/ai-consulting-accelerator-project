// Minimal Cognito auth for the consulting demo pool (admin-created users only,
// no self sign-up). Uses direct Cognito IDP REST calls — no Amplify dependency.
// The id token is kept in localStorage and sent as a Bearer token to the API.

import { useSyncExternalStore } from "react";

const REGION = process.env.NEXT_PUBLIC_CONSULTING_COGNITO_REGION ?? "eu-central-1";
const CLIENT_ID = process.env.NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID ?? "";
const COGNITO_URL = `https://cognito-idp.${REGION}.amazonaws.com/`;

const TOKEN_KEY = "consulting_id_token";
const EXPIRY_KEY = "consulting_token_expiry";
const EMAIL_KEY = "consulting_email";

export interface Auth {
  idToken: string;
  email: string;
  expiresAt: number;
}

function cognito(target: string, body: Record<string, unknown>): Promise<Response> {
  return fetch(COGNITO_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  });
}

export async function login(email: string, password: string): Promise<Auth> {
  if (!CLIENT_ID) {
    throw new Error(
      "Auth is not configured. Set NEXT_PUBLIC_CONSULTING_COGNITO_CLIENT_ID (run scripts/setup_consulting_cognito.py).",
    );
  }
  const res = await cognito("InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: CLIENT_ID,
    AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.message ?? `Login failed (${res.status})`);
  }
  if (data.ChallengeName) {
    // Admin-created users need a permanent password; see the setup script.
    throw new Error(
      `Account requires a password reset (${data.ChallengeName}). Ask the admin to set a permanent password.`,
    );
  }
  const result = data.AuthenticationResult;
  const auth: Auth = {
    idToken: result.IdToken,
    email,
    expiresAt: Date.now() + result.ExpiresIn * 1000,
  };
  localStorage.setItem(TOKEN_KEY, auth.idToken);
  localStorage.setItem(EXPIRY_KEY, String(auth.expiresAt));
  localStorage.setItem(EMAIL_KEY, auth.email);
  notify();
  return auth;
}

export function getAuth(): Auth | null {
  if (typeof window === "undefined") return null;
  const idToken = localStorage.getItem(TOKEN_KEY);
  const expiresAt = Number(localStorage.getItem(EXPIRY_KEY) ?? 0);
  const email = localStorage.getItem(EMAIL_KEY) ?? "";
  if (!idToken || Date.now() >= expiresAt) return null;
  return { idToken, email, expiresAt };
}

export function isAuthenticated(): boolean {
  return getAuth() !== null;
}

export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRY_KEY);
  localStorage.removeItem(EMAIL_KEY);
  notify();
}

// ── React store for auth state (SSR-safe, no setState-in-effect) ──────────────

const listeners = new Set<() => void>();

function notify(): void {
  for (const cb of listeners) cb();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

// Cache the snapshot keyed by the token string so useSyncExternalStore gets a
// stable reference between renders (required to avoid an infinite loop).
let cachedToken: string | null = null;
let cachedAuth: Auth | null = null;

function getSnapshot(): Auth | null {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token !== cachedToken) {
    cachedToken = token;
    cachedAuth = getAuth();
  }
  return cachedAuth;
}

export function useAuth(): Auth | null {
  return useSyncExternalStore(subscribe, getSnapshot, () => null);
}
