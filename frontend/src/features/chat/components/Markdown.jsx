import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/*
 * Renders assistant replies as GitHub-flavored Markdown, mapped onto the app's
 * semantic design tokens so it themes (light/dark) with everything else.
 * Kept compact to fit the chat bubble width.
 */

const components = {
  p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-semibold text-content">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="my-1.5 list-disc space-y-1 pl-5 marker:text-subtle">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1.5 list-decimal space-y-1 pl-5 marker:text-subtle">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{children}</li>,
  h1: ({ children }) => (
    <h1 className="mt-2 mb-1 text-base font-semibold text-content first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-2 mb-1 text-sm font-semibold text-content first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-2 mb-1 text-sm font-semibold text-content first:mt-0">
      {children}
    </h3>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-1.5 border-l-2 border-border-strong pl-3 text-muted">
      {children}
    </blockquote>
  ),
  code: ({ inline, children }) =>
    inline ? (
      <code className="rounded bg-surface-inset px-1.5 py-0.5 font-mono text-[0.8em] text-content">
        {children}
      </code>
    ) : (
      <code className="font-mono text-[0.8em]">{children}</code>
    ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-xl bg-surface-inset p-3 text-[0.8em] text-content">
      {children}
    </pre>
  ),
  hr: () => <hr className="my-3 border-border-default" />,
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border border-border-default text-left text-xs">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-2">{children}</thead>,
  th: ({ children }) => (
    <th className="border border-border-default px-2.5 py-1.5 font-semibold text-content">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border-default px-2.5 py-1.5 align-top">
      {children}
    </td>
  ),
};

function Markdown({ children }) {
  return (
    <div className="text-sm leading-relaxed text-content [overflow-wrap:anywhere]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export default Markdown;
