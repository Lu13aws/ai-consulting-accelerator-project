import type { SourceReference } from "@/lib/api";

export default function Sources({ sources }: { sources: SourceReference[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Sources</h2>
      <ol className="flex flex-col gap-2">
        {sources.map((s, i) => (
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
  );
}
