import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Markdown({ children }: { children: string }) {
  return (
    <article className="prose prose-sm prose-zinc max-w-none rounded-lg border border-zinc-200 bg-white p-4 dark:prose-invert dark:border-zinc-800 dark:bg-zinc-900">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </article>
  );
}
