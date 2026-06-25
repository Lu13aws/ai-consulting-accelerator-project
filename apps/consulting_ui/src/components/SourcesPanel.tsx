"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import type { SourceReference } from "@/lib/api";

export default function SourcesPanel({ sources }: { sources: SourceReference[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;
  return (
    <div className="mt-3 border border-slate-700 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-slate-400 bg-slate-800 hover:bg-slate-700 transition-colors"
      >
        <span>
          {sources.length} source{sources.length !== 1 ? "s" : ""}
        </span>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div className="divide-y divide-slate-700">
          {sources.map((s, i) => (
            <div key={s.chunk_id} className="px-3 py-2 bg-slate-900">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono text-slate-500">[{i + 1}]</span>
                <span className="text-xs text-blue-400 truncate">{s.source_uri}</span>
                <span className="text-xs text-slate-600 ml-auto shrink-0">
                  {(s.score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-xs text-slate-500 line-clamp-2">{s.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
