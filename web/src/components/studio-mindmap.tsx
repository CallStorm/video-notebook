import { useEffect, useRef } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import type { INode, IPureNode } from "markmap-common";
import { Maximize2, Minimize2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { discussPrompt } from "@/lib/studio-discuss";

export interface MindMapSource {
  id: number;
  title: string;
}

type BoundNode = Element & { __data__?: INode };

export function StudioMindmap({
  title,
  text,
  notice,
  noticeError,
  videos,
  notes,
  expanded,
  onBack,
  onToggleExpanded,
  onOpenVideo,
  onOpenNote,
  onDiscuss,
}: {
  title: string;
  text: string | null;
  notice: string | null;
  noticeError?: boolean;
  videos: MindMapSource[];
  notes: MindMapSource[];
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
  onOpenVideo: (videoId: number) => void;
  onOpenNote: (noteId: number) => void;
  onDiscuss: (message: string) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const markmapRef = useRef<Markmap | null>(null);
  const discussRef = useRef(onDiscuss);
  discussRef.current = onDiscuss;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || text == null) return;
    const { root } = new Transformer().transform(text);
    const markmap = Markmap.create(svg, undefined, root);
    markmapRef.current = markmap;
    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("circle")) return;
      const foreign = target.closest("foreignObject");
      const group = target.closest("g.markmap-node");
      if (!foreign || !group) return;
      const node = (group as BoundNode).__data__ ?? (foreign as BoundNode).__data__;
      const data = markmap.state.data;
      if (!node || !data) return;
      const current = plainText(node.content);
      if (!current) return;
      const anchor = target.closest("a");
      if (anchor) event.preventDefault();
      const parent = parentOf(data, node);
      discussRef.current(discussPrompt(current, parent ? plainText(parent.content) : null));
    };
    svg.addEventListener("click", onClick);
    return () => {
      svg.removeEventListener("click", onClick);
      markmap.destroy();
      if (markmapRef.current === markmap) markmapRef.current = null;
    };
  }, [text]);

  function zoom(scale: number) {
    void markmapRef.current?.rescale(scale);
  }

  function expandAll() {
    const markmap = markmapRef.current;
    const data = markmap?.state.data;
    if (!markmap || !data) return;
    clearFold(data);
    void markmap.setData(data);
  }

  function download() {
    if (text == null) return;
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const shell = expanded
    ? "fixed inset-0 z-40 flex flex-col bg-background"
    : "flex min-h-0 flex-1 flex-col bg-background";

  return (
    <div className={shell}>
      <header className="flex shrink-0 items-start justify-between gap-2 border-b px-3 py-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
              Studio
            </button>
            <span className="px-1">›</span>
            <span className="text-foreground">{title}</span>
          </p>
          {videos.length > 0 || notes.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {videos.map((video) => (
                <button
                  key={`video-${video.id}`}
                  type="button"
                  title="打开视频"
                  className="max-w-[14rem] truncate rounded-full border px-2 py-0.5 text-[11px] hover:bg-muted"
                  onClick={() => onOpenVideo(video.id)}
                >
                  {video.title}
                </button>
              ))}
              {notes.map((note) => (
                <button
                  key={`note-${note.id}`}
                  type="button"
                  title="打开笔记"
                  className="max-w-[14rem] truncate rounded-full border px-2 py-0.5 text-[11px] hover:bg-muted"
                  onClick={() => onOpenNote(note.id)}
                >
                  {note.title}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center">
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            title={expanded ? "还原" : "铺满"}
            onClick={onToggleExpanded}
          >
            {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
          <Button size="icon" variant="ghost" className="h-7 w-7" title="返回 Studio" onClick={onBack}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>
      {notice ? (
        <p className={`p-4 text-sm ${noticeError ? "text-destructive" : "text-muted-foreground"}`}>{notice}</p>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className="flex w-[4.75rem] shrink-0 flex-col gap-1 border-r p-2">
            <ToolbarButton label="放大" onClick={() => zoom(1.25)} />
            <ToolbarButton label="缩小" onClick={() => zoom(0.8)} />
            <ToolbarButton label="适应" onClick={() => void markmapRef.current?.fit()} />
            <ToolbarButton label="全部展开" onClick={expandAll} />
            <ToolbarButton label="下载" onClick={download} />
          </div>
          <div className="min-h-0 min-w-0 flex-1">
            <svg ref={svgRef} className="h-full w-full" />
          </div>
        </div>
      )}
    </div>
  );
}

function ToolbarButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="rounded px-1 py-1 text-left text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function plainText(html: string): string {
  const holder = document.createElement("div");
  holder.innerHTML = html;
  return (holder.textContent ?? "").replace(/\s+/g, " ").trim();
}

function parentOf(root: INode, node: INode): INode | null {
  let found: INode | null = null;
  const visit = (current: INode, parent: INode | null) => {
    if (found) return;
    if (current.state.id === node.state.id) {
      found = parent;
      return;
    }
    for (const child of current.children) visit(child, current);
  };
  visit(root, null);
  return found;
}

function clearFold(node: IPureNode) {
  if (node.payload) node.payload.fold = 0;
  for (const child of node.children) clearFold(child);
}
