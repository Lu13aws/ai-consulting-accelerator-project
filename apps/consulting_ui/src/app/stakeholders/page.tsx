"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import Markdown from "@/components/Markdown";
import SourcesPanel from "@/components/SourcesPanel";
import { api, type StructureResponse } from "@/lib/api";

export default function StakeholdersPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StructureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.stakeholders(input));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-100">Stakeholder Analysis</h1>
        <p className="text-sm text-slate-500 mt-1">
          A RACI matrix skeleton, suggested stakeholder categories and engagement levels,
          grounded in the BABOK stakeholder analysis knowledge area.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-slate-400">
            Project &amp; known stakeholders<span className="text-blue-400"> *</span>
          </span>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe your project and known stakeholders…"
            rows={6}
            style={{ minHeight: 120 }}
            className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
          />
        </label>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading ? "Analysing…" : "Analyse"}
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
