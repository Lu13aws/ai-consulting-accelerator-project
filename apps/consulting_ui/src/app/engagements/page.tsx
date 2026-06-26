"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import Markdown from "@/components/Markdown";
import { api, type EngagementDetail, type EngagementSummary } from "@/lib/api";

function isConcluded(status: string): boolean {
  return status === "concluded" || status === "refined"; // "refined" = legacy
}

function StatusBadge({ status }: { status: string }) {
  const concluded = isConcluded(status);
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        concluded ? "bg-green-950 text-green-300" : "bg-blue-950 text-blue-300"
      }`}
    >
      {concluded ? "Concluded" : "In discovery"}
    </span>
  );
}

function Section({ title, body }: { title: string; body: string | null }) {
  if (!body) return null;
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      <div className="bg-slate-900 border border-slate-800 rounded-lg px-5 py-4">
        <Markdown>{body}</Markdown>
      </div>
    </div>
  );
}

function ListView() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<EngagementSummary[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.listEngagements();
        if (!cancelled) setItems(res.engagements);
      } catch {
        // listing is best-effort
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      const eng = await api.createEngagement(input);
      router.push(`/engagements?id=${eng.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setCreating(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-100">Engagements</h1>
        <p className="text-sm text-slate-500 mt-1">
          A guided, multi-step discovery: describe the situation → review analysis,
          hypotheses &amp; open questions → answer → get a refined analysis and requirements.
        </p>
      </div>

      <form onSubmit={create} className="flex flex-col gap-3 mb-8">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe the customer's situation or problem in free text…"
          rows={5}
          style={{ minHeight: 120 }}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={creating || !input.trim()}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
          >
            {creating && <Loader2 size={14} className="animate-spin" />}
            {creating ? "Starting discovery…" : "Start engagement"}
          </button>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>

      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Recent</h2>
      {items.length === 0 ? (
        <p className="text-sm text-slate-600">No engagements yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((e) => (
            <li key={e.id}>
              <Link
                href={`/engagements?id=${e.id}`}
                className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300 hover:border-blue-700 hover:bg-slate-800 transition-colors"
              >
                <span className="flex-1 truncate">{e.title}</span>
                <StatusBadge status={e.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DetailView({ id }: { id: string }) {
  const [eng, setEng] = useState<EngagementDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [concluding, setConcluding] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const e = await api.getEngagement(id);
        if (!cancelled) setEng(e);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Not found");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function submitAnswers(e: React.FormEvent) {
    e.preventDefault();
    if (!answers.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      setEng(await api.answerEngagement(id, answers));
      setAnswers("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function conclude() {
    if (concluding) return;
    setConcluding(true);
    setError(null);
    try {
      setEng(await api.concludeEngagement(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setConcluding(false);
    }
  }

  async function generate(tool: string) {
    if (generating) return;
    setGenerating(tool);
    setError(null);
    try {
      setEng(await api.generateFromEngagement(id, tool));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setGenerating(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-8 py-10 text-sm text-slate-500">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    );
  }
  if (error && !eng) {
    return <div className="px-8 py-10 text-sm text-red-400">{error}</div>;
  }
  if (!eng) return null;

  const concluded = isConcluded(eng.status);
  const busy = submitting || concluding || generating !== null;
  const currentQuestions = eng.turns.length
    ? eng.turns[eng.turns.length - 1].open_questions
    : eng.open_questions;

  return (
    <div className="max-w-3xl mx-auto px-8 py-8 flex flex-col gap-6">
      <div>
        <Link href="/engagements" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-400">
          <ArrowLeft size={12} /> All engagements
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-100">{eng.title}</h1>
          <StatusBadge status={eng.status} />
        </div>
      </div>

      <Section title="Initial Analysis" body={eng.initial_analysis} />
      <Section title="Hypotheses" body={eng.hypotheses} />

      {/* Discovery rounds */}
      {eng.turns.map((t, i) => (
        <div key={i} className="flex flex-col gap-4 border-l-2 border-slate-800 pl-4">
          <Section title={`Round ${i + 1} — Your answers`} body={t.answers ?? null} />
          <Section title={`Round ${i + 1} — Updated findings`} body={t.findings ?? null} />
        </div>
      ))}

      {/* Legacy engagements (pre-turns) kept their answers/refined in columns */}
      {eng.turns.length === 0 && eng.refined_analysis && (
        <>
          <Section title="Answers" body={eng.answers} />
          <Section title="Refined Analysis" body={eng.refined_analysis} />
        </>
      )}

      {!concluded && (
        <>
          <Section title="Open Questions" body={currentQuestions} />
          <form onSubmit={submitAnswers} className="flex flex-col gap-3">
            <textarea
              value={answers}
              onChange={(e) => setAnswers(e.target.value)}
              placeholder="Answer the open questions above…"
              rows={5}
              style={{ minHeight: 120 }}
              className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={conclude}
                disabled={busy}
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2.5 text-sm text-slate-300 transition-colors hover:border-green-600 hover:text-green-400 disabled:opacity-40"
              >
                {concluding && <Loader2 size={14} className="animate-spin" />}
                Conclude &amp; synthesize
              </button>
              <button
                type="submit"
                disabled={busy || !answers.trim()}
                className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                {submitting ? "Refining…" : "Submit answers"}
              </button>
            </div>
            <p className="text-xs text-slate-600">
              Submit answers to dig deeper (another round), or conclude to synthesize
              requirements &amp; a consultant assessment.
            </p>
            {error && <p className="text-sm text-red-400">{error}</p>}
          </form>
        </>
      )}

      {concluded && (
        <>
          <Section title="Requirements" body={eng.requirements} />
          <Section title="Consultant's Assessment" body={eng.assessment} />

          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Continue with this engagement
            </h2>
            <div className="flex flex-wrap gap-2">
              {[
                { tool: "roadmap", label: "Roadmap" },
                { tool: "stakeholders", label: "Stakeholder Analysis" },
              ].map(({ tool, label }) => (
                <button
                  key={tool}
                  onClick={() => generate(tool)}
                  disabled={generating !== null}
                  className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-blue-600 hover:text-blue-400 disabled:opacity-40"
                >
                  {generating === tool && <Loader2 size={14} className="animate-spin" />}
                  {eng.extras[tool] ? `Regenerate ${label}` : `Generate ${label}`}
                </button>
              ))}
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
          </div>

          <Section title="Roadmap" body={eng.extras.roadmap ?? null} />
          <Section title="Stakeholder Analysis" body={eng.extras.stakeholders ?? null} />
        </>
      )}
    </div>
  );
}

function EngagementsInner() {
  const id = useSearchParams().get("id");
  return id ? <DetailView id={id} /> : <ListView />;
}

export default function EngagementsPage() {
  return (
    <Suspense>
      <EngagementsInner />
    </Suspense>
  );
}
