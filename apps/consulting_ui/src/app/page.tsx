"use client";

import { useState } from "react";

import Markdown from "@/components/Markdown";
import Sources from "@/components/Sources";
import { query, type QueryResponse } from "@/lib/api";

const EXAMPLES = [
  "What are the knowledge areas in BABOK?",
  "Erkläre den Unterschied zwischen funktionalen und nicht-funktionalen Anforderungen laut IREB.",
  "What makes a good user story according to INVEST?",
];

export default function Home() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await query(trimmed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Framework Q&amp;A</h1>
        <p className="text-sm text-slate-400">
          Framework Q&amp;A grounded in IREB, BABOK, BPMN, PMBOK and related standards.
          Answers cite their sources and follow your language (DE/EN).
        </p>
      </header>

      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSubmit(e);
          }}
          placeholder="Ask a question about the frameworks…"
          rows={3}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 p-3 text-sm text-slate-200 placeholder-slate-600 outline-none transition-colors focus:border-blue-600"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-slate-600">⌘/Ctrl + Enter to send</span>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </form>

      {!result && !loading && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuestion(ex);
                void ask(ex);
              }}
              className="rounded-full border border-slate-700 px-3 py-1 text-left text-xs text-slate-400 transition hover:border-blue-600 hover:text-blue-400"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-900 bg-red-950 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <Markdown>{result.answer}</Markdown>
          <Sources sources={result.sources} />
          <p className="text-[11px] text-slate-600">
            AI-generated draft grounded in cited frameworks — requires human review.
            Model: {result.model} · {result.input_tokens + result.output_tokens} tokens.
          </p>
        </section>
      )}
    </main>
  );
}
