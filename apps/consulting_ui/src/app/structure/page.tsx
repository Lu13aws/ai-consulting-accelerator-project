"use client";

import { useEffect, useMemo, useState } from "react";

import Markdown from "@/components/Markdown";
import Sources from "@/components/Sources";
import {
  getSkills,
  structure,
  type SkillInfo,
  type StructureResponse,
} from "@/lib/api";

function fieldLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StructurePage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StructureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSkills()
      .then((res) => {
        setSkills(res.skills);
        if (res.skills.length > 0) setSelected(res.skills[0].name);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load skills"));
  }, []);

  const skill = useMemo(() => skills.find((s) => s.name === selected), [skills, selected]);

  function selectSkill(name: string) {
    if (name === selected) return;
    setSelected(name);
    setInputs({});
    setResult(null);
    setError(null);
  }

  const missingRequired = skill?.required_fields.some((f) => !(inputs[f] ?? "").trim()) ?? true;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!skill || missingRequired || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await structure(skill.name, inputs));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Structure an Artifact</h1>
        <p className="text-sm text-zinc-500">
          Turn raw input into an IREB/BABOK-aligned draft. Outputs are grounded in cited
          frameworks and follow your language (DE/EN).
        </p>
      </header>

      {skills.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {skills.map((s) => (
            <button
              key={s.name}
              onClick={() => selectSkill(s.name)}
              className={`rounded-full border px-3 py-1 text-xs transition ${
                s.name === selected
                  ? "border-zinc-900 bg-zinc-900 text-white dark:border-white dark:bg-white dark:text-zinc-900"
                  : "border-zinc-300 text-zinc-600 hover:border-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
              }`}
            >
              {s.name.replace("consulting.", "")}
            </button>
          ))}
        </div>
      )}

      {skill && (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <p className="text-xs text-zinc-500">
            {skill.description}{" "}
            <span className="text-zinc-400">(v{skill.version})</span>
          </p>

          {[...skill.required_fields, ...skill.optional_fields].map((field) => {
            const required = skill.required_fields.includes(field);
            return (
              <label key={field} className="flex flex-col gap-1">
                <span className="text-sm font-medium">
                  {fieldLabel(field)}
                  {required ? <span className="text-red-500"> *</span> : (
                    <span className="text-zinc-400"> (optional)</span>
                  )}
                </span>
                <textarea
                  value={inputs[field] ?? ""}
                  onChange={(e) => setInputs((prev) => ({ ...prev, [field]: e.target.value }))}
                  rows={field === skill.required_fields[0] ? 5 : 3}
                  className="w-full resize-y rounded-lg border border-zinc-300 bg-white p-3 text-sm shadow-sm outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
                />
              </label>
            );
          })}

          <div className="flex items-center justify-end">
            <button
              type="submit"
              disabled={loading || missingRequired}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-zinc-900"
            >
              {loading ? "Structuring…" : "Structure"}
            </button>
          </div>
        </form>
      )}

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <Markdown>{result.artifact}</Markdown>
          <Sources sources={result.sources} />
          <p className="text-[11px] text-zinc-400">
            {result.skill} v{result.version} · Model: {result.model} ·{" "}
            {result.input_tokens + result.output_tokens} tokens.
          </p>
        </section>
      )}
    </main>
  );
}
