// Typed client for the consulting API (/api/v1/consulting/*).
// Base URL configurable via NEXT_PUBLIC_API_URL (defaults to localhost:8000).
// When Cognito is configured (deployed build), requests carry a Bearer token and a 401
// sends the user back to /login; locally (no auth) it behaves as an open API.

import { AUTH_ENABLED, getToken, logout } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASE = `${API_URL}/api/v1/consulting`;

function authHeaders(): Record<string, string> {
  const token = AUTH_ENABLED ? getToken() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function on401(status: number): void {
  if (AUTH_ENABLED && status === 401 && typeof window !== "undefined") {
    logout();
    window.location.href = "/login";
  }
}

export interface SourceReference {
  chunk_id: string;
  source_uri: string;
  score: number;
  excerpt: string;
  category: string | null;
  language: string | null;
}

export interface QueryResponse {
  answer: string;
  sources: SourceReference[];
  model: string;
  input_tokens: number;
  output_tokens: number;
}

export interface StructureResponse {
  skill: string;
  version: string;
  artifact: string;
  sources: SourceReference[];
  model: string;
  input_tokens: number;
  output_tokens: number;
}

export interface SkillInfo {
  name: string;
  version: string;
  description: string;
  layer: string;
  required_fields: string[];
  optional_fields: string[];
}

export interface EngagementSummary {
  id: string;
  title: string;
  status: string;
  archived: boolean;
  created_at: string;
}

export interface EngagementDetail {
  id: string;
  title: string;
  status: string;
  archived: boolean;
  language: string;
  initial_input: string;
  initial_analysis: string | null;
  hypotheses: string | null;
  open_questions: string | null;
  answers: string | null;
  refined_analysis: string | null;
  requirements: string | null;
  assessment: string | null;
  extras: Record<string, string>;
  turns: { answers: string | null; findings: string | null; open_questions: string | null }[];
  created_at: string;
  updated_at: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { ...authHeaders() } });
  if (!res.ok) {
    on401(res.status);
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    on401(res.status);
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // no JSON body
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    on401(res.status);
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers: { ...authHeaders() } });
  if (!res.ok) {
    on401(res.status);
    throw new Error(`${res.status} ${res.statusText}`);
  }
}

export const api = {
  query: (question: string) => post<QueryResponse>("/query", { question }),
  structureProblem: (problem_description: string, additional_context?: string) =>
    post<StructureResponse>("/structure/problem", { problem_description, additional_context }),
  structureRequirements: (requirements: string, context?: string) =>
    post<StructureResponse>("/structure/requirements", { requirements, context }),
  structureRoadmap: (input: {
    vision: string;
    goals: string;
    known_scope?: string;
    constraints?: string;
    target_users?: string;
  }) => post<StructureResponse>("/structure/roadmap", input),
  stakeholders: (input: string) => post<StructureResponse>("/stakeholders", { input }),
  getSkills: () => getJSON<{ skill_count: number; skills: SkillInfo[] }>("/skills"),
  runSkill: (skill: string, inputs: Record<string, string>) =>
    post<StructureResponse>("/run", { skill, inputs }),

  // Engagements (Phase 2 — Interview/Discovery Mode)
  createEngagement: (input: string) => post<EngagementDetail>("/engagements", { input }),
  listEngagements: (includeArchived = false) =>
    getJSON<{ count: number; engagements: EngagementSummary[] }>(
      `/engagements${includeArchived ? "?include_archived=true" : ""}`,
    ),
  getEngagement: (id: string) => getJSON<EngagementDetail>(`/engagements/${id}`),
  updateEngagement: (id: string, body: { title?: string; archived?: boolean }) =>
    patch<EngagementDetail>(`/engagements/${id}`, body),
  deleteEngagement: (id: string) => del(`/engagements/${id}`),
  answerEngagement: (id: string, answers: string) =>
    post<EngagementDetail>(`/engagements/${id}/answer`, { answers }),
  concludeEngagement: (id: string) =>
    post<EngagementDetail>(`/engagements/${id}/conclude`, {}),
  generateFromEngagement: (id: string, tool: string) =>
    post<EngagementDetail>(`/engagements/${id}/generate`, { tool }),
  // Auth-aware download: fetch with the Bearer header (a plain <a> can't send it under JWT),
  // then trigger a browser download from the blob.
  downloadReport: async (id: string, format: "md" | "docx" | "pdf") => {
    const res = await fetch(`${BASE}/engagements/${id}/report?format=${format}`, {
      headers: { ...authHeaders() },
    });
    if (!res.ok) {
      on401(res.status);
      throw new Error(`${res.status} ${res.statusText}`);
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") ?? "";
    const match = cd.match(/filename="?([^"]+)"?/);
    const name = match ? match[1] : `engagement.${format}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
