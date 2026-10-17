import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { visit } from "unist-util-visit";
import type { ChatCitation } from "@/components/notebook-chat";

type TextNode = { type: "text"; value: string };
type ParentNode = { type: string; children: Array<TextNode | { type: "link"; url: string; children: TextNode[] }> };

/** 把字幕引用 [12] 变成链接，后面再画成可点的编号。代码块里的原文不动。 */
function remarkCitations() {
  return (tree: ParentNode) => {
    visit(tree, "text", (node: TextNode, index: number | undefined, parent: ParentNode | undefined) => {
      if (parent == null || index == null) return;
      if (parent.type === "link" || parent.type === "linkReference") return;
      if (!/\[\d+\]/.test(node.value)) return;
      const next: ParentNode["children"] = [];
      const pattern = /\[(\d+)\]/g;
      let last = 0;
      for (const match of node.value.matchAll(pattern)) {
        const start = match.index ?? 0;
        if (start > last) next.push({ type: "text", value: node.value.slice(last, start) });
        const n = match[1];
        next.push({ type: "link", url: `#cite-${n}`, children: [{ type: "text", value: n }] });
        last = start + match[0].length;
      }
      if (last < node.value.length) next.push({ type: "text", value: node.value.slice(last) });
      parent.children.splice(index, 1, ...next);
      return index + next.length;
    });
  };
}

export function MarkdownMessage({
  text,
  citations,
  onJump,
}: {
  text: string;
  citations: ChatCitation[];
  onJump: (videoId: number, lineNo: number) => void;
}) {
  const byNumber = new Map(citations.map((citation) => [citation.n, citation]));
  const components: Components = {
    p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
    ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
    li: ({ children }) => <li>{children}</li>,
    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
    h1: ({ children }) => <h3 className="mb-1 mt-3 text-base font-semibold first:mt-0">{children}</h3>,
    h2: ({ children }) => <h3 className="mb-1 mt-3 text-base font-semibold first:mt-0">{children}</h3>,
    h3: ({ children }) => <h4 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h4>,
    h4: ({ children }) => <h4 className="mb-1 mt-2 text-sm font-semibold first:mt-0">{children}</h4>,
    blockquote: ({ children }) => (
      <blockquote className="my-2 border-l-2 border-foreground/20 pl-3 text-muted-foreground">{children}</blockquote>
    ),
    hr: () => <hr className="my-3 border-border" />,
    pre: ({ children }) => (
      <pre className="my-2 overflow-x-auto rounded-lg bg-background p-3 text-xs leading-5">{children}</pre>
    ),
    code: ({ className, children }) =>
      className ? (
        <code className={className}>{children}</code>
      ) : (
        <code className="rounded bg-background px-1 py-0.5 text-[0.85em]">{children}</code>
      ),
    table: ({ children }) => (
      <div className="my-2 overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">{children}</table>
      </div>
    ),
    th: ({ children }) => (
      <th className="border border-border bg-background px-2 py-1 font-medium">{children}</th>
    ),
    td: ({ children }) => <td className="border border-border px-2 py-1 align-top">{children}</td>,
    a: ({ href, children }) => {
      const cite = /^#cite-(\d+)$/.exec(href ?? "");
      if (cite) {
        const n = Number(cite[1]);
        return <CitationMark n={n} citation={byNumber.get(n)} onJump={onJump} />;
      }
      if (href && /^https?:\/\//i.test(href)) {
        return (
          <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">
            {children}
          </a>
        );
      }
      return <span>{children}</span>;
    },
  };

  return (
    <div className="text-sm leading-6">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

function CitationMark({
  n,
  citation,
  onJump,
}: {
  n: number;
  citation: ChatCitation | undefined;
  onJump: (videoId: number, lineNo: number) => void;
}) {
  const className =
    "mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-foreground px-1 align-text-bottom text-[11px] font-semibold leading-none text-background";
  if (!citation || !Number.isFinite(n)) {
    return <span className={className}>{Number.isFinite(n) ? n : "?"}</span>;
  }
  const title = [citation.title, citation.snippet].filter(Boolean).join(" · ");
  return (
    <button
      type="button"
      title={title}
      className={`${className} hover:opacity-80`}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onJump(citation.source_id, citation.line_no);
      }}
    >
      {n}
    </button>
  );
}
