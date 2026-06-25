"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";

import Markdown from "@/components/Markdown";
import SourcesPanel from "@/components/SourcesPanel";
import { api, type QueryResponse } from "@/lib/api";

type Message =
  | { role: "user"; content: string }
  | { role: "assistant"; response: QueryResponse };

const SUGGESTED = [
  "What are the BABOK knowledge areas?",
  "Erkläre den Unterschied zwischen funktionalen und nicht-funktionalen Anforderungen laut IREB",
  "What is the INVEST criteria for user stories?",
  "How does BPMN model decision gateways?",
  "What does the HBR guide say about project sponsor roles?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submit(question: string) {
    if (!question.trim() || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const response = await api.query(question);
      setMessages((m) => [...m, { role: "assistant", response }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          response: {
            answer: `Error: ${e instanceof Error ? e.message : String(e)}`,
            sources: [],
            model: "",
            input_tokens: 0,
            output_tokens: 0,
          },
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto">
      <div className="px-8 py-6 border-b border-slate-800">
        <h1 className="text-2xl font-semibold text-slate-100">Framework Q&amp;A</h1>
        <p className="text-sm text-slate-500 mt-1">
          Answers grounded in IREB, BABOK, BPMN, PMBOK and related standards — with citations.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-500 mb-4">Suggested questions:</p>
            {SUGGESTED.map((q) => (
              <button
                key={q}
                onClick={() => submit(q)}
                className="block w-full text-left px-4 py-3 rounded-lg border border-slate-800 bg-slate-900 text-sm text-slate-300 hover:border-blue-700 hover:bg-slate-800 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="max-w-lg bg-blue-600/20 border border-blue-700/40 rounded-lg px-4 py-3">
                  <p className="text-sm text-slate-200">{msg.content}</p>
                </div>
              </div>
            ) : (
              <div className="max-w-3xl">
                <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-4">
                  <Markdown>{msg.response.answer}</Markdown>
                  {msg.response.model && (
                    <p className="text-xs text-slate-600 mt-2">
                      {msg.response.model} · {msg.response.input_tokens + msg.response.output_tokens} tokens
                    </p>
                  )}
                </div>
                <SourcesPanel sources={msg.response.sources} />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 size={14} className="animate-spin" />
            Thinking…
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="px-8 py-5 border-t border-slate-800">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit(input)}
            placeholder="Ask the Framework Knowledge Base…"
            className="flex-1 px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-600 transition-colors"
            disabled={loading}
          />
          <button
            onClick={() => submit(input)}
            disabled={loading || !input.trim()}
            className="px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 rounded-lg text-sm font-medium text-white transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
