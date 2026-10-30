import { useEffect, useRef, useState } from "react";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import type { INode } from "markmap-common";
import { Download, Maximize2, Minus, Minimize2, Plus, Scan, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { discussPrompt } from "@/lib/studio-discuss";

export interface MindMapSource {
  id: number;
  title: string;
}

type BoundNode = Element & { __data__?: INode };

const LEVEL_COLORS = ["#1e3a8a", "#115e59", "#9a3412", "#5b21b6", "#9f1239", "#075985", "#3f6212", "#92400e"];

const NODE_STYLE = `
.markmap-foreign > div > div {
  border-radius: 8px;
  padding: 6px 12px;
  font: 600 14px/1.45 ui-sans-serif, system-ui, sans-serif;
  color: #ffffff;
}
.markmap-node > line {
  display: none;
}
`;

type MarkmapLink = { source: INode; target: INode };

function levelColor(node: INode): string {
  const depth = Math.max(node.state?.depth ?? 1, 1);
  return LEVEL_COLORS[(depth - 1) % LEVEL_COLORS.length] ?? LEVEL_COLORS[0];
}

function linkPath(x1: number, y1: number, x2: number, y2: number): string {
  const mid = (x1 + x2) / 2;
  return `M${x1},${y1}C${mid},${y1},${mid},${y2},${x2},${y2}`;
}

function connectNodes(markmap: Markmap) {
  const paddingX = markmap.options.paddingX;
  const svg = markmap.svg;
  svg.selectAll("g.markmap-node > line").interrupt();
  svg.selectAll<SVGCircleElement, INode>("g.markmap-node > circle").interrupt().attr("cx", (node: INode) => node.state.rect.width - paddingX).attr("cy", (node: INode) => node.state.rect.height / 2);
  svg.selectAll<SVGPathElement, MarkmapLink>("path.markmap-link").interrupt().attr("fill", "none").attr("stroke", (link: MarkmapLink) => levelColor(link.target)).attr("stroke-width", (link: MarkmapLink) => Math.max(2, markmap.options.lineWidth(link.target))).attr("d", (link: MarkmapLink) => {
    const source = link.source.state.rect;
    const target = link.target.state.rect;
    return linkPath(
      source.x + source.width - paddingX,
      source.y + source.height / 2,
      target.x + paddingX,
      target.y + target.height / 2,
    );
  });
}

function paintNodeBackgrounds(markmap: Markmap) {
  const root = markmap.svg.node();
  if (!root) return;
  root.querySelectorAll("g.markmap-node").forEach((group: Element) => {
    const node = (group as BoundNode).__data__;
    const label = group.querySelector(".markmap-foreign > div > div");
    if (!node || !(label instanceof HTMLElement)) return;
    label.style.backgroundColor = levelColor(node);
    label.style.color = "#ffffff";
  });
}

export function StudioMindmap({
  title,
  crumb,
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
  crumb: string;
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
  const [sourcesOpen, setSourcesOpen] = useState(false);
  discussRef.current = onDiscuss;
  const sourceCount = videos.length + notes.length;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || text == null) return;
    const { root } = new Transformer().transform(text);
    const markmap = new Markmap(svg, {
      scrollForPan: false,
      pan: false,
      zoom: true,
      spacingVertical: 16,
      spacingHorizontal: 88,
      paddingX: 8,
      color: levelColor,
      style: () => NODE_STYLE,
    });
    const render = markmap.renderData.bind(markmap);
    markmap.renderData = async (origin) => {
      await render(origin);
      connectNodes(markmap);
      paintNodeBackgrounds(markmap);
    };
    void markmap.setData(root);
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
  }, [text, expanded]);

  useEffect(() => {
    if (text == null) return;
    const frame = window.requestAnimationFrame(() => {
      void markmapRef.current?.fit();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [expanded, text]);

  function zoom(scale: number) {
    void markmapRef.current?.rescale(scale);
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
      <div className="flex items-center justify-between px-5 pt-4">
        <p className="min-w-0 truncate text-sm text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
            产物
          </button>
          <span className="px-1.5">›</span>
          <span className="text-foreground">{crumb}</span>
        </p>
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
          <button
            type="button"
            title="关闭"
            className="rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={onBack}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="px-5 pb-2 pt-4">
        <h2 className={expanded ? "text-2xl font-semibold tracking-tight" : "text-lg font-semibold tracking-tight"}>
          {title}
        </h2>
        {sourceCount > 0 ? (
          <div className="relative mt-3">
            <button
              type="button"
              className="rounded-full border px-3 py-1 text-sm hover:bg-muted"
              onClick={() => setSourcesOpen((open) => !open)}
            >
              {sourceCount === 1 ? "View 1 source" : `View ${sourceCount} sources`}
            </button>
            {sourcesOpen ? (
              <div className="absolute left-0 top-full z-10 mt-2 w-64 overflow-hidden rounded-xl border bg-popover py-1 text-popover-foreground shadow-lg">
                {videos.map((video) => (
                  <button
                    key={`video-${video.id}`}
                    type="button"
                    className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => onOpenVideo(video.id)}
                  >
                    {video.title}
                  </button>
                ))}
                {notes.map((note) => (
                  <button
                    key={`note-${note.id}`}
                    type="button"
                    className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => onOpenNote(note.id)}
                  >
                    {note.title}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
      {notice ? (
        <p className={`px-5 py-4 text-sm ${noticeError ? "text-destructive" : "text-muted-foreground"}`}>{notice}</p>
      ) : (
        <div className="relative min-h-0 flex-1">
          <div className="absolute left-4 top-4 z-10 flex flex-col gap-2">
            <RoundButton label="适应" onClick={() => void markmapRef.current?.fit()}>
              <Scan className="h-4 w-4" />
            </RoundButton>
            <RoundButton label="放大" onClick={() => zoom(1.25)}>
              <Plus className="h-4 w-4" />
            </RoundButton>
            <RoundButton label="缩小" onClick={() => zoom(0.8)}>
              <Minus className="h-4 w-4" />
            </RoundButton>
            <RoundButton label="下载" onClick={download}>
              <Download className="h-4 w-4" />
            </RoundButton>
          </div>
          <div className="h-full pl-16">
            <svg ref={svgRef} className="h-full w-full" />
          </div>
        </div>
      )}
    </div>
  );
}

function RoundButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      className="flex h-10 w-10 items-center justify-center rounded-full border bg-background text-foreground shadow-sm hover:bg-muted"
      onClick={onClick}
    >
      {children}
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
