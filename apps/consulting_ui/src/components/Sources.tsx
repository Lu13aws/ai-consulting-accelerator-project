import type { SourceReference } from "@/lib/api";

export default function Sources({ sources }: { sources: SourceReference[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</h2>
      <ol className="flex flex-col gap-2">
        {sources.map((s, i) => (
          <li
            key={s.chunk_id}
            className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-xs"
          >
            <div className="mb-1 flex flex-wrap items-center gap-2 font-medium text-slate-300">
              <span className="text-blue-400">[{i + 1}]</span>
              <span className="font-mono">{s.source_uri}</span>
              {s.category && (
                <span className="rounded bg-blue-950 px-1.5 py-0.5 text-[10px] text-blue-300">
                  {s.category}
                  {s.language && s.language !== "unknown" ? ` · ${s.language}` : ""}
                </span>
              )}
              <span className="ml-auto text-slate-500">score {s.score.toFixed(3)}</span>
            </div>
            <p className="text-slate-400">{s.excerpt}…</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
