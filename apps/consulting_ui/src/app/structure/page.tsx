"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

import Markdown from "@/components/Markdown";
import SourcesPanel from "@/components/SourcesPanel";
import { api, type StructureResponse } from "@/lib/api";

type TabId = "problem" | "requirements" | "roadmap";

interface FieldDef {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  rows: number;
}

const TABS: { id: TabId; label: string; fields: FieldDef[]; submit: (f: Record<string, string>) => Promise<StructureResponse> }[] = [
  {
    id: "problem",
    label: "Business Problem",
    fields: [
      { key: "problem_description", label: "Business problem", placeholder: "Describe your business problem…", required: true, rows: 6 },
    ],
    submit: (f) => api.structureProblem(f.problem_description),
  },
  {
    id: "requirements",
    label: "Requirements",
    fields: [
      { key: "requirements", label: "Raw requirements", placeholder: "Paste your raw requirements here…", required: true, rows: 6 },
    ],
    submit: (f) => api.structureRequirements(f.requirements),
  },
  {
    id: "roadmap",
    label: "Roadmap",
    fields: [
      { key: "vision", label: "Product / project vision", placeholder: "What are you building, for whom, and why?", required: true, rows: 3 },
      { key: "goals", label: "Goals / outcomes", placeholder: "Target outcomes, ideally measurable", required: true, rows: 2 },
      { key: "known_scope", label: "Known scope / features", placeholder: "Known features or scope items (optional)", required: false, rows: 2 },
      { key: "constraints", label: "Constraints / timeline", placeholder: "Deadlines, team, budget, tech (optional)", required: false, rows: 2 },
      { key: "target_users", label: "Target users / stakeholders", placeholder: "Who are the users / stakeholders? (optional)", required: false, rows: 2 },
    ],
    submit: (f) =>
      api.structureRoadmap({
        vision: f.vision,
        goals: f.goals,
        known_scope: f.known_scope,
        constraints: f.constraints,
        target_users: f.target_users,
      }),
  },
];

function StructureInner() {
  const searchParams = useSearchParams();
  const initial = (searchParams.get("tab") as TabId) || "problem";
  const [tab, setTab] = useState<TabId>(TABS.some((t) => t.id === initial) ? initial : "problem");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StructureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const active = useMemo(() => TABS.find((t) => t.id === tab)!, [tab]);
  const missingRequired = active.fields.some((f) => f.required && !(fields[f.key] ?? "").trim());

  function switchTab(id: TabId) {
    if (id === tab) return;
    setTab(id);
    setFields({});
    setResult(null);
    setError(null);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (missingRequired || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await active.submit(fields));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-100">Structurer</h1>
        <p className="text-sm text-slate-500 mt-1">
          Turn raw input into an IREB/BABOK-aligned draft. Grounded in cited frameworks,
          follows your language (DE/EN).
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-800 mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => switchTab(t.id)}
            className={`px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px ${
              t.id === tab
                ? "border-blue-500 text-slate-100 font-medium"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {active.fields.map((f) => (
          <label key={f.key} className="flex flex-col gap-1.5">
            <span className="text-xs text-slate-400">
              {f.label}
              {f.required ? <span className="text-blue-400"> *</span> : <span className="text-slate-600"> (optional)</span>}
            </span>
            <textarea
              value={fields[f.key] ?? ""}
              onChange={(e) => setFields((prev) => ({ ...prev, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
              rows={f.rows}
              style={{ minHeight: f.rows >= 6 ? 120 : undefined }}
              className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
            />
          </label>
        ))}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || missingRequired}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {loading ? "Structuring…" : "Structure"}
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

export default function StructurePage() {
  return (
    <Suspense>
      <StructureInner />
    </Suspense>
  );
}
