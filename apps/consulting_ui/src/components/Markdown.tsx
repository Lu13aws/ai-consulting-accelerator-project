import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ children }: { children: string }) {
  return (
    <article className="prose prose-sm prose-slate max-w-none rounded-lg border border-slate-200 bg-white p-4 prose-headings:text-slate-900 prose-a:text-blue-700">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </article>
  );
}
