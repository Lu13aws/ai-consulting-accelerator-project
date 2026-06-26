// Typed client for the consulting API (/api/v1/consulting/*). Public demo — no auth.
// Base URL configurable via NEXT_PUBLIC_API_URL (defaults to localhost:8000).

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASE = `${API_URL}/api/v1/consulting`;

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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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
      // no JSON body
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
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
};
