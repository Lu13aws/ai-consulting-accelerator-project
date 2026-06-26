"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import Markdown from "@/components/Markdown";
import SourcesPanel from "@/components/SourcesPanel";
import { api, type StructureResponse } from "@/lib/api";

// Single-input discovery aids (all take one free-text "context" field).
const TOOLS = [
  { skill: "consulting.identify-risks", label: "Risks", placeholder: "Describe the project / situation to assess for risks…" },
  { skill: "consulting.detect-assumptions", label: "Assumptions", placeholder: "Describe the project to surface implicit assumptions…" },
  { skill: "consulting.open-questions", label: "Open Questions", placeholder: "Describe what you know so far — we'll list what's still open…" },
  { skill: "consulting.generate-hypotheses", label: "Hypotheses", placeholder: "Describe the problem whose root cause is unclear…" },
  { skill: "consulting.interview-guide", label: "Interview Guide", placeholder: "Describe the project to build a discovery interview guide…" },
  { skill: "consulting.consultant-assessment", label: "Consultant Assessment", placeholder: "Describe the situation for an initial assessment + prioritisation…" },
];

function DiscoveryInner() {
  const searchParams = useSearchParams();
  const initial = searchParams.get("skill") ?? "";
  const [skill, setSkill] = useState(
    TOOLS.some((t) => t.skill === initial) ? initial : TOOLS[0].skill,
  );
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StructureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = useMemo(() => TOOLS.find((t) => t.skill === skill)!, [skill]);

  function select(s: string) {
    if (s === skill) return;
    setSkill(s);
    setText("");
    setResult(null);
    setError(null);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.runSkill(skill, { context: text }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-100">Discovery</h1>
        <p className="text-sm text-slate-500 mt-1">
          Quick discovery aids — risks, assumptions, open questions, hypotheses and an
          interview guide. Drafts grounded in cited frameworks; follows your language (DE/EN).
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {TOOLS.map((t) => (
          <button
            key={t.skill}
            onClick={() => select(t.skill)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              t.skill === skill
                ? "border-blue-600 bg-blue-600 text-white"
                : "border-slate-700 text-slate-400 hover:border-blue-600 hover:text-blue-400"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={active.placeholder}
          rows={6}
          style={{ minHeight: 120 }}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading ? "Working…" : "Generate"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-6 p-4 bg-red-900/20 border border-red-800 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6">
          <div className="bg-slate-900 border border-slate-800 rounded-lg px-5 py-4">
            <Markdown>{result.artifact}</Markdown>
            <p className="text-xs text-slate-600 mt-3">
              {result.skill} v{result.version} · {result.model} ·{" "}
              {result.input_tokens + result.output_tokens} tokens
            </p>
          </div>
          <SourcesPanel sources={result.sources} />
        </div>
      )}
    </div>
  );
}

export default function DiscoveryPage() {
  return (
    <Suspense>
      <DiscoveryInner />
    </Suspense>
  );
}
