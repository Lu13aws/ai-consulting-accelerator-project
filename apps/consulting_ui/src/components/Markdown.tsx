import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ children }: { children: string }) {
  return (
    <article className="prose prose-sm prose-invert max-w-none rounded-lg border border-slate-800 bg-slate-900 p-4 prose-headings:text-slate-100 prose-a:text-blue-400">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </article>
  );
}
