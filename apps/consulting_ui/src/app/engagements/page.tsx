"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import Markdown from "@/components/Markdown";
import { api, type EngagementDetail, type EngagementSummary } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const refined = status === "refined";
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        refined ? "bg-green-950 text-green-300" : "bg-blue-950 text-blue-300"
      }`}
    >
      {refined ? "Refined" : "Awaiting answers"}
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-8 py-10 text-sm text-slate-500">
        <Loader2 size={16} className="animate-spin" /> Loading…
      </div>
    );
  }
  if (error || !eng) {
    return <div className="px-8 py-10 text-sm text-red-400">{error ?? "Not found"}</div>;
  }

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
      <Section title="Open Questions" body={eng.open_questions} />

      {eng.status === "awaiting_answers" ? (
        <form onSubmit={submitAnswers} className="flex flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Your answers
          </h2>
          <textarea
            value={answers}
            onChange={(e) => setAnswers(e.target.value)}
            placeholder="Answer the open questions above…"
            rows={5}
            style={{ minHeight: 120 }}
            className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || !answers.trim()}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? "Refining…" : "Submit answers"}
            </button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </form>
      ) : (
        <>
          <Section title="Answers" body={eng.answers} />
          <Section title="Refined Analysis" body={eng.refined_analysis} />
          <Section title="Requirements" body={eng.requirements} />
          <Section title="Consultant's Assessment" body={eng.assessment} />
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
