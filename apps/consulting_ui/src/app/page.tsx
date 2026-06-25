"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
        <h1 className="text-2xl font-semibold tracking-tight">AI Consulting Accelerator</h1>
        <p className="text-sm text-zinc-500">
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
          className="w-full resize-y rounded-lg border border-zinc-300 bg-white p-3 text-sm shadow-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-zinc-400">⌘/Ctrl + Enter to send</span>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-zinc-900"
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
              className="rounded-full border border-zinc-300 px-3 py-1 text-left text-xs text-zinc-600 transition hover:border-zinc-500 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-400"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <article className="prose prose-sm prose-zinc max-w-none rounded-lg border border-zinc-200 bg-white p-4 dark:prose-invert dark:border-zinc-800 dark:bg-zinc-900">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
          </article>

          {result.sources.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                Sources
              </h2>
              <ol className="flex flex-col gap-2">
                {result.sources.map((s, i) => (
                  <li
                    key={s.chunk_id}
                    className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900"
                  >
                    <div className="mb-1 flex flex-wrap items-center gap-2 font-medium text-zinc-700 dark:text-zinc-300">
                      <span>[{i + 1}]</span>
                      <span className="font-mono">{s.source_uri}</span>
                      {s.category && (
                        <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                          {s.category}
                          {s.language && s.language !== "unknown" ? ` · ${s.language}` : ""}
                        </span>
                      )}
                      <span className="ml-auto text-zinc-400">score {s.score.toFixed(3)}</span>
                    </div>
                    <p className="text-zinc-500">{s.excerpt}…</p>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <p className="text-[11px] text-zinc-400">
            AI-generated draft grounded in cited frameworks — requires human review.
            Model: {result.model} · {result.input_tokens + result.output_tokens} tokens.
          </p>
        </section>
      )}
    </main>
  );
}
