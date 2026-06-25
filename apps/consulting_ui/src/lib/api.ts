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

export function query(question: string, topK = 5): Promise<QueryResponse> {
  return postJSON<QueryResponse>("/api/v1/query", { question, top_k: topK });
}
