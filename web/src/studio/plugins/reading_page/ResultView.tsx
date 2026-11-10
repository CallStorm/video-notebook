import { useMemo, useRef, useState } from "react";
import { ChevronDown, Download, Maximize2, Minimize2, Play, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { parseClockToSeconds } from "@/components/studio-notes";

export interface ReadingSource {
  id: number;
  title: string;
}

type DiagramKind = "flow" | "compare" | "sequence";

interface ReadingStep {
  title?: string;
  body: string;
  time?: string;
  videoId?: number;
  quote?: string;
  aside?: string;
}

interface ReadingNode {
  label: string;
  detail?: string;
}

interface ReadingDiagram {
  kind: DiagramKind;
  caption?: string;
  nodes: ReadingNode[];
}

interface ReadingSection {
  id: string;
  title: string;
  summary?: string;
  steps: ReadingStep[];
  diagram?: ReadingDiagram;
}

interface ReadingPageData {
  title?: string;
  kicker?: string;
  theme: string;
  lede?: string;
  sections: ReadingSection[];
  closing?: string;
}

function textOf(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const text = value.trim();
  return text || undefined;
}

function videoIdOf(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  if (typeof value === "string" && /^\d+$/.test(value.trim())) {
    const id = Number(value.trim());
    return id > 0 ? id : undefined;
  }
  return undefined;
}

function clockOf(value: unknown): string | undefined {
  const text = textOf(value);
  if (!text || parseClockToSeconds(text) == null) return undefined;
  return text;
}

function sectionId(value: unknown, index: number): string {
  const text = textOf(value);
  if (text && /^[A-Za-z][\w-]{0,40}$/.test(text)) return text;
  return `section-${index + 1}`;
}

function parseNodes(value: unknown): ReadingNode[] {
  if (!Array.isArray(value)) return [];
  const nodes: ReadingNode[] = [];
  for (const item of value) {
    if (typeof item === "string") {
      const label = item.trim();
      if (label) nodes.push({ label });
      continue;
    }
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const label = textOf(row.label);
    if (!label) continue;
    nodes.push({ label, detail: textOf(row.detail) });
  }
  return nodes;
}

function parseDiagram(value: unknown): ReadingDiagram | undefined {
  if (!value || typeof value !== "object") return undefined;
  const row = value as Record<string, unknown>;
  const nodes = parseNodes(row.nodes);
  if (nodes.length < 2) return undefined;
  const kind = row.kind === "compare" || row.kind === "sequence" || row.kind === "flow" ? row.kind : "flow";
  return { kind, caption: textOf(row.caption), nodes: nodes.slice(0, 6) };
}

function parseStep(value: unknown): ReadingStep | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const body = textOf(row.body);
  const title = textOf(row.title);
  if (!body && !title) return null;
  return {
    title,
    body: body || title || "",
    time: clockOf(row.time),
    videoId: videoIdOf(row.video_id),
    quote: textOf(row.quote),
    aside: textOf(row.aside),
  };
}

function parseSections(value: unknown): ReadingSection[] {
  if (!Array.isArray(value)) return [];
  const sections: ReadingSection[] = [];
  value.forEach((item) => {
    if (!item || typeof item !== "object") return;
    const row = item as Record<string, unknown>;
    const title = textOf(row.title);
    if (!title) return;
    const steps = Array.isArray(row.steps)
      ? row.steps.map(parseStep).filter((step): step is ReadingStep => step != null)
      : [];
    if (steps.length === 0) return;
    const id = sectionId(row.id, sections.length);
    sections.push({
      id: sections.some((section) => section.id === id) ? `section-${sections.length + 1}` : id,
      title,
      summary: textOf(row.summary),
      steps,
      diagram: parseDiagram(row.diagram),
    });
  });
  return sections;
}

function parseReadingPage(text: string | null): ReadingPageData | null {
  if (!text) return null;
  const trimmed = text.trim().replace(/^\uFEFF/, "");
  if (!trimmed.startsWith("{")) return null;
  try {
    const data = JSON.parse(trimmed) as unknown;
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    const row = data as Record<string, unknown>;
    const sections = parseSections(row.sections);
    if (sections.length === 0) return null;
    return {
      title: textOf(row.title),
      kicker: textOf(row.kicker),
      theme: textOf(row.theme) || "",
      lede: textOf(row.lede),
      sections,
      closing: textOf(row.closing),
    };
  } catch {
    return null;
  }
}

function seekVideoId(step: ReadingStep, videos: ReadingSource[]): number | null {
  if (step.videoId != null) return step.videoId;
  if (videos.length === 1) return videos[0].id;
  return null;
}

export function StudioReadingPage({
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
  onSeekVideo,
}: {
  title: string;
  crumb: string;
  text: string | null;
  notice: string | null;
  noticeError?: boolean;
  videos: ReadingSource[];
  notes: ReadingSource[];
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
  onOpenVideo: (videoId: number) => void;
  onOpenNote: (noteId: number) => void;
  onSeekVideo?: (videoId: number, timeSec: number) => void;
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});
  const page = useMemo(() => parseReadingPage(text), [text]);
  const sourceCount = videos.length + notes.length;
  const docTitle = page?.title || title || "阅读页";
  const seekableCount =
    page?.sections.reduce((count, section) => {
      return (
        count +
        section.steps.filter((step) => step.time && seekVideoId(step, videos) != null).length
      );
    }, 0) ?? 0;

  function scrollToSection(id: string) {
    sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function download() {
    if (!text) return;
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${docTitle}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function jump(step: ReadingStep) {
    if (!step.time) return;
    const videoId = seekVideoId(step, videos);
    const seconds = parseClockToSeconds(step.time);
    if (videoId == null || seconds == null) {
      if (videos[0]) onOpenVideo(videos[0].id);
      return;
    }
    if (onSeekVideo) onSeekVideo(videoId, seconds);
    else onOpenVideo(videoId);
  }

  const shell = expanded
    ? "fixed inset-0 z-40 flex flex-col bg-background"
    : "flex min-h-0 flex-1 flex-col bg-background";

  return (
    <div className={shell}>
      <div className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-3">
        <p className="min-w-0 truncate text-sm text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
            产物
          </button>
          <span className="px-1.5">›</span>
          <span className="text-foreground">{crumb}</span>
        </p>
        <div className="flex shrink-0 items-center">
          {text ? (
            <Button size="icon" variant="ghost" className="h-7 w-7" title="下载" onClick={download}>
              <Download className="h-3.5 w-3.5" />
            </Button>
          ) : null}
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

      {notice ? (
        <p className={`px-6 py-8 text-sm ${noticeError ? "text-destructive" : "text-muted-foreground"}`}>{notice}</p>
      ) : !page ? (
        <p className="px-6 py-8 text-sm text-muted-foreground">阅读页内容无法解析</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <article className="mx-auto w-full max-w-[40rem] px-6 py-8 sm:px-8 sm:py-10">
            {page.kicker ? (
              <p className="text-xs font-medium tracking-[0.14em] text-primary">{page.kicker}</p>
            ) : null}
            <h1
              className={`text-[1.65rem] font-semibold leading-tight tracking-tight text-foreground ${page.kicker ? "mt-2" : ""} ${expanded ? "sm:text-3xl" : ""}`}
            >
              {docTitle}
            </h1>
            {sourceCount > 0 ? (
              <div className="relative mt-4">
                <button
                  type="button"
                  className="rounded-full border border-border/70 bg-card px-3 py-1 text-xs text-muted-foreground hover:border-primary/30 hover:text-foreground"
                  onClick={() => setSourcesOpen((open) => !open)}
                >
                  {sourceCount === 1 ? "1 个来源" : `${sourceCount} 个来源`}
                  {seekableCount > 0 ? ` · ${seekableCount} 处可跳转` : ""}
                </button>
                {sourcesOpen ? (
                  <div className="absolute left-0 top-full z-10 mt-2 w-64 overflow-hidden rounded-xl border bg-popover py-1 text-popover-foreground shadow-lg">
                    {videos.map((video) => (
                      <button
                        key={`video-${video.id}`}
                        type="button"
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => {
                          setSourcesOpen(false);
                          onOpenVideo(video.id);
                        }}
                      >
                        {video.title}
                      </button>
                    ))}
                    {notes.map((note) => (
                      <button
                        key={`note-${note.id}`}
                        type="button"
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => {
                          setSourcesOpen(false);
                          onOpenNote(note.id);
                        }}
                      >
                        {note.title}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {page.theme ? (
              <aside className="mt-7 border-l-4 border-primary bg-primary/[0.06] px-4 py-3.5">
                <p className="text-xs font-semibold tracking-wide text-primary">主题</p>
                <p className="mt-1.5 text-base font-medium leading-7 text-foreground">{page.theme}</p>
              </aside>
            ) : null}

            {page.lede ? (
              <p className="mt-6 text-[15px] leading-7 text-foreground/90">{page.lede}</p>
            ) : null}

            {page.sections.length > 1 ? (
              <nav aria-label="目录" className="mt-8">
                <p className="text-xs font-semibold tracking-wide text-muted-foreground">目录</p>
                <ol className="mt-2.5 space-y-1.5 border-l border-border pl-4">
                  {page.sections.map((section, index) => (
                    <li key={section.id}>
                      <button
                        type="button"
                        className="text-left text-sm leading-6 text-foreground/90 hover:text-primary"
                        onClick={() => scrollToSection(section.id)}
                      >
                        <span className="mr-2 font-mono text-xs text-muted-foreground">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        {section.title}
                      </button>
                    </li>
                  ))}
                </ol>
              </nav>
            ) : null}

            {page.sections.map((section, sectionIndex) => (
              <section
                key={section.id}
                id={section.id}
                ref={(node) => {
                  sectionRefs.current[section.id] = node;
                }}
                className="mt-11 scroll-mt-6"
              >
                <h2 className="text-xl font-semibold tracking-tight text-foreground">
                  <span className="mr-2 font-mono text-sm font-medium text-primary/80">
                    {String(sectionIndex + 1).padStart(2, "0")}
                  </span>
                  {section.title}
                </h2>
                {section.summary ? (
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{section.summary}</p>
                ) : null}
                <div className="mt-5 space-y-6">
                  {section.steps.map((step, stepIndex) => {
                    const canSeek = step.time != null && seekVideoId(step, videos) != null;
                    return (
                      <div key={`${section.id}-${stepIndex}`} className="grid grid-cols-[1.6rem_minmax(0,1fr)] gap-x-3">
                        <div className="pt-0.5 text-sm font-semibold text-primary">{stepIndex + 1}</div>
                        <div className="min-w-0">
                          {step.title && step.title !== step.body ? (
                            <h3 className="text-[15px] font-semibold leading-6 text-foreground">{step.title}</h3>
                          ) : null}
                          <p className={`${step.title && step.title !== step.body ? "mt-1.5" : ""} text-[15px] leading-7 text-foreground/90`}>
                            {step.body}
                          </p>
                          {step.quote ? (
                            <blockquote className="mt-3 border-l-2 border-primary/35 pl-3 text-sm italic leading-7 text-muted-foreground">
                              {step.quote}
                            </blockquote>
                          ) : null}
                          {step.aside ? (
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.aside}</p>
                          ) : null}
                          {step.time ? (
                            canSeek ? (
                              <button
                                type="button"
                                className="mt-2 inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline"
                                title="跳到原片"
                                onClick={() => jump(step)}
                              >
                                <Play className="h-3 w-3 fill-current" />
                                {step.time}
                              </button>
                            ) : (
                              <span className="mt-2 inline-flex items-center gap-1 font-mono text-xs text-muted-foreground">
                                {step.time}
                              </span>
                            )
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {section.diagram ? <ReadingDiagramView diagram={section.diagram} /> : null}
              </section>
            ))}

            {page.closing ? (
              <section className="mt-12 border-t border-border/80 pt-6">
                <h2 className="text-lg font-semibold tracking-tight">收束</h2>
                <p className="mt-3 text-[15px] leading-7 text-foreground/90">{page.closing}</p>
              </section>
            ) : null}
          </article>
        </div>
      )}
    </div>
  );
}

function ReadingDiagramView({ diagram }: { diagram: ReadingDiagram }) {
  if (diagram.kind === "compare") {
    return (
      <figure className="mt-6">
        <div className={`grid gap-3 ${diagram.nodes.length === 2 ? "grid-cols-2" : "sm:grid-cols-2"}`}>
          {diagram.nodes.map((node, index) => (
            <div key={`${node.label}-${index}`} className="rounded-xl border border-border/80 bg-card px-3 py-3">
              <div className="text-sm font-semibold leading-6">{node.label}</div>
              {node.detail ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{node.detail}</p> : null}
            </div>
          ))}
        </div>
        {diagram.caption ? <figcaption className="mt-2 text-xs leading-5 text-muted-foreground">{diagram.caption}</figcaption> : null}
      </figure>
    );
  }

  if (diagram.kind === "sequence") {
    return (
      <figure className="mt-6">
        <ol className="flex flex-wrap items-center gap-2">
          {diagram.nodes.map((node, index) => (
            <li key={`${node.label}-${index}`} className="flex items-center gap-2">
              {index > 0 ? <span className="text-sm text-muted-foreground">→</span> : null}
              <span className="rounded-full border border-border/80 bg-card px-3 py-1 text-sm">
                <span className="mr-1.5 font-mono text-xs text-primary">{index + 1}</span>
                {node.label}
              </span>
            </li>
          ))}
        </ol>
        {diagram.caption ? <figcaption className="mt-2 text-xs leading-5 text-muted-foreground">{diagram.caption}</figcaption> : null}
      </figure>
    );
  }

  return (
    <figure className="mt-6">
      <div className="space-y-1">
        {diagram.nodes.map((node, index) => (
          <div key={`${node.label}-${index}`}>
            {index > 0 ? (
              <div className="flex justify-center py-0.5 text-primary/60" aria-hidden>
                <ChevronDown className="h-4 w-4" />
              </div>
            ) : null}
            <div className="rounded-xl border border-border/80 bg-card px-3 py-2.5">
              <div className="text-sm font-medium leading-6">{node.label}</div>
              {node.detail ? <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{node.detail}</p> : null}
            </div>
          </div>
        ))}
      </div>
      {diagram.caption ? <figcaption className="mt-2 text-xs leading-5 text-muted-foreground">{diagram.caption}</figcaption> : null}
    </figure>
  );
}

export { StudioReadingPage as ResultView };
