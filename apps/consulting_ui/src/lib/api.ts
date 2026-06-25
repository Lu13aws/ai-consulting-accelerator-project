// Typed client for the consulting API. Base URL is configurable via
// NEXT_PUBLIC_API_URL (defaults to localhost:8000 for local dev).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export interface SkillInfo {
  name: string;
  version: string;
  description: string;
  required_fields: string[];
  optional_fields: string[];
}

export interface SkillsResponse {
  skill_count: number;
  skills: SkillInfo[];
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

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // response had no JSON body — keep the status-line detail
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function query(question: string, topK = 5): Promise<QueryResponse> {
  return postJSON<QueryResponse>("/api/v1/query", { question, top_k: topK });
}

export function getSkills(): Promise<SkillsResponse> {
  return getJSON<SkillsResponse>("/api/v1/skills");
}

export function structure(
  skill: string,
  inputs: Record<string, string>,
  topK = 6,
): Promise<StructureResponse> {
  return postJSON<StructureResponse>("/api/v1/structure", { skill, inputs, top_k: topK });
}
