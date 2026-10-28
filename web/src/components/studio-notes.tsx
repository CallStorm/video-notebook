import { useMemo, useState, type ReactNode } from "react";
import { BookOpen, CheckCircle2, Clock3, Download, Lightbulb, Maximize2, Minimize2, Quote, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface NotesSource {
  id: number;
  title: string;
}

type Concept = { term: string; definition: string };
type Point = { time?: string; text: string };
type Evidence = { text: string };

export type StructuredNotesData = {
  theme?: string;
  concepts: Concept[];
  points: Point[];
  evidence: Evidence[];
  takeaways: string[];
  rawMarkdown?: string;
};

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

/** Parse MM:SS or HH:MM:SS (optional surrounding punctuation) into seconds. */
export function parseClockToSeconds(raw: string | undefined | null): number | null {
  if (!raw) return null;
  const cleaned = raw.trim().replace(/^[\[【(（`]+|[\]】)）`]+$/g, "");
  const m = /^(\d{1,2}):([0-5]?\d)(?::([0-5]?\d))?$/.exec(cleaned);
  if (!m) return null;
  const a = Number(m[1]);
  const b = Number(m[2]);
  const c = m[3] != null ? Number(m[3]) : null;
  if ([a, b, c].some((n) => n != null && Number.isNaN(n))) return null;
  if (c != null) return a * 3600 + b * 60 + c;
  return a * 60 + b;
}

function extractLeadingTime(text: string): { time?: string; text: string } {
  const m = /^`?(\d{1,2}:\d{2}(?::\d{2})?)`?\s*[\]】)）:]?\s*(.+)$/s.exec(text.trim());
  if (m && parseClockToSeconds(m[1]) != null) return { time: m[1], text: m[2].trim() };
  return { text: text.trim() };
}

function parseNotes(text: string | null): StructuredNotesData | null {
  if (!text || !text.trim()) return null;
  const trimmed = text.trim();
  if (trimmed.startsWith("{")) {
    try {
      const data = JSON.parse(trimmed) as Record<string, unknown>;
      const concepts: Concept[] = [];
      for (const item of asList(data.concepts)) {
        if (!item || typeof item !== "object") continue;
        const row = item as Record<string, unknown>;
        const term = typeof row.term === "string" ? row.term.trim() : "";
        const definition = typeof row.definition === "string" ? row.definition.trim() : "";
        if (term || definition) concepts.push({ term: term || "概念", definition });
      }
      const points: Point[] = [];
      for (const item of asList(data.points)) {
        if (!item || typeof item !== "object") continue;
        const row = item as Record<string, unknown>;
        const textValue = typeof row.text === "string" ? row.text.trim() : "";
        if (!textValue) continue;
        const explicit = typeof row.time === "string" ? row.time.trim() : "";
        if (explicit && parseClockToSeconds(explicit) != null) {
          points.push({ time: explicit, text: textValue });
        } else {
          const extracted = extractLeadingTime(textValue);
          points.push(extracted.time ? extracted : { text: textValue });
        }
      }
      const evidence: Evidence[] = [];
      for (const item of asList(data.evidence)) {
        if (!item || typeof item !== "object") continue;
        const row = item as Record<string, unknown>;
        const textValue = typeof row.text === "string" ? row.text.trim() : "";
        if (textValue) evidence.push({ text: textValue });
      }
      const takeaways = asList(data.takeaways)
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean);
      return {
        theme: typeof data.theme === "string" ? data.theme.trim() : undefined,
        concepts,
        points,
        evidence,
        takeaways,
      };
    } catch {
      /* fall through to markdown */
    }
  }
  return parseMarkdownNotes(trimmed);
}

function parseMarkdownNotes(text: string): StructuredNotesData {
  const sections: Record<string, string[]> = {};
  let current = "theme";
  sections[current] = [];
  for (const line of text.split(/\r?\n/)) {
    const heading = /^(#{1,3})\s+(.+)$/.exec(line.trim());
    if (heading) {
      const title = heading[2].trim();
      if (/主题/.test(title)) current = "theme";
      else if (/概念/.test(title)) current = "concepts";
      else if (/要点|时间/.test(title)) current = "points";
      else if (/论据|证据|原文/.test(title)) current = "evidence";
      else if (/结论|行动|清单|takeaway/i.test(title)) current = "takeaways";
      else if (heading[1] === "#" && !sections.theme?.length) {
        sections.theme = [title];
        continue;
      } else current = "other";
      if (!sections[current]) sections[current] = [];
      continue;
    }
    if (!sections[current]) sections[current] = [];
    if (line.trim()) sections[current].push(line.trim());
  }

  const concepts: Concept[] = [];
  for (const line of sections.concepts ?? []) {
    const cleaned = line.replace(/^[-*]\s*/, "");
    const m = /^\*\*(.+?)\*\*[：:]\s*(.+)$/.exec(cleaned) || /^([^：:]+)[：:]\s*(.+)$/.exec(cleaned);
    if (m) concepts.push({ term: m[1].trim(), definition: m[2].trim() });
    else if (cleaned) concepts.push({ term: cleaned, definition: "" });
  }

  const points: Point[] = [];
  for (const line of sections.points ?? []) {
    const cleaned = line.replace(/^[-*]\s*/, "");
    const extracted = extractLeadingTime(cleaned);
    if (extracted.text) points.push(extracted);
  }

  const evidence = (sections.evidence ?? [])
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean)
    .map((textValue) => ({ text: textValue }));

  const takeaways = (sections.takeaways ?? [])
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);

  const themeLines = sections.theme ?? [];
  return {
    theme: themeLines[0]?.replace(/^[-*]\s*/, "") || undefined,
    concepts,
    points,
    evidence,
    takeaways,
    rawMarkdown: text,
  };
}

function Section({
  icon,
  title,
  count,
  children,
}: {
  icon: ReactNode;
  title: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <section className="mb-6">
      <div className="mb-2.5 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-soft">
          {icon}
        </span>
        <h3 className="text-sm font-semibold tracking-tight text-foreground">{title}</h3>
        {count != null && count > 0 ? <span className="panel-count">{count}</span> : null}
      </div>
      {children}
    </section>
  );
}

export function StudioNotes({
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
  videos: NotesSource[];
  notes: NotesSource[];
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
  onOpenVideo: (videoId: number) => void;
  onOpenNote: (noteId: number) => void;
  onSeekVideo?: (videoId: number, timeSec: number) => void;
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const parsed = useMemo(() => parseNotes(text), [text]);
  const sourceCount = videos.length + notes.length;
  const primaryVideoId = videos[0]?.id;
  const timedCount = parsed?.points.filter((p) => p.time && parseClockToSeconds(p.time) != null).length ?? 0;

  function download() {
    if (!text) return;
    const jsonLike = text.trim().startsWith("{");
    const blob = new Blob([text], {
      type: jsonLike ? "application/json;charset=utf-8" : "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title || "结构化笔记"}${jsonLike ? ".json" : ".md"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function handleTimeClick(time: string) {
    if (primaryVideoId == null) return;
    const sec = parseClockToSeconds(time);
    if (sec == null) {
      onOpenVideo(primaryVideoId);
      return;
    }
    if (onSeekVideo) onSeekVideo(primaryVideoId, sec);
    else onOpenVideo(primaryVideoId);
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-gradient-to-b from-card via-card to-accent/20">
      <div className="flex items-center gap-2 border-b border-border/60 px-4 py-2.5">
        <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={onBack}>
          Studio
        </button>
        <span className="text-xs text-muted-foreground/70">/</span>
        <span className="truncate text-xs text-muted-foreground">{crumb}</span>
        <div className="ml-auto flex items-center gap-1">
          <Button size="icon" variant="ghost" className="h-8 w-8 rounded-full" title="下载" onClick={download}>
            <Download className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 rounded-full"
            title={expanded ? "缩小" : "放大"}
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

      <div className="px-5 pb-3 pt-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-soft">
            <BookOpen className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className={expanded ? "text-2xl font-semibold tracking-tight" : "text-lg font-semibold tracking-tight"}>
              {title}
            </h2>
            {sourceCount > 0 ? (
              <div className="relative mt-2.5">
                <button
                  type="button"
                  className="rounded-full border border-border/70 bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-soft transition hover:border-primary/30 hover:text-foreground"
                  onClick={() => setSourcesOpen((open) => !open)}
                >
                  {sourceCount === 1 ? "1 个来源" : `${sourceCount} 个来源`}
                  {timedCount > 0 ? ` · ${timedCount} 处可跳转` : ""}
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
          </div>
        </div>
      </div>

      {notice ? (
        <p className={`px-5 py-4 text-sm ${noticeError ? "text-destructive" : "text-muted-foreground"}`}>{notice}</p>
      ) : !parsed ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">暂无内容</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-10">
          {parsed.theme ? (
            <div className="mb-6 overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/10 via-card to-accent/40 p-4 shadow-soft">
              <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                主题
              </div>
              <p className="text-sm font-medium leading-relaxed text-foreground">{parsed.theme}</p>
            </div>
          ) : null}

          {parsed.concepts.length > 0 ? (
            <Section icon={<Lightbulb className="h-3.5 w-3.5" />} title="关键概念" count={parsed.concepts.length}>
              <div className={`grid gap-2 ${expanded ? "sm:grid-cols-2" : "grid-cols-1"}`}>
                {parsed.concepts.map((concept, index) => (
                  <div
                    key={`${concept.term}-${index}`}
                    className="rounded-2xl border border-border/60 bg-card/90 p-3 shadow-soft transition hover:border-primary/25"
                  >
                    <div className="text-sm font-semibold text-foreground">{concept.term}</div>
                    {concept.definition ? (
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{concept.definition}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </Section>
          ) : null}

          {parsed.points.length > 0 ? (
            <Section icon={<Clock3 className="h-3.5 w-3.5" />} title="要点" count={parsed.points.length}>
              <ol className="space-y-2">
                {parsed.points.map((point, index) => {
                  const seekable = point.time != null && parseClockToSeconds(point.time) != null && primaryVideoId != null;
                  return (
                    <li
                      key={`${point.time ?? ""}-${index}`}
                      className="flex gap-3 rounded-2xl border border-border/60 bg-card/90 px-3 py-2.5 shadow-soft"
                    >
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-muted-foreground">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        {point.time ? (
                          <button
                            type="button"
                            className="mb-1 inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-primary transition hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={!seekable && primaryVideoId == null}
                            title={
                              seekable
                                ? "跳转到视频对应时间"
                                : primaryVideoId == null
                                  ? "没有可播放的来源视频"
                                  : "打开来源视频"
                            }
                            onClick={() => handleTimeClick(point.time!)}
                          >
                            <Clock3 className="h-3 w-3" />
                            {point.time}
                          </button>
                        ) : null}
                        <p className="text-sm leading-relaxed text-foreground">{point.text}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>
              {timedCount === 0 && primaryVideoId != null ? (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  本篇要点未标注时间戳，可点上方来源打开视频；重新生成时尽量保留字幕时间。
                </p>
              ) : null}
            </Section>
          ) : null}

          {parsed.evidence.length > 0 ? (
            <Section icon={<Quote className="h-3.5 w-3.5" />} title="论据 / 原文要点" count={parsed.evidence.length}>
              <ul className="space-y-2">
                {parsed.evidence.map((item, index) => (
                  <li
                    key={index}
                    className="rounded-2xl border border-border/50 border-l-[3px] border-l-primary/40 bg-muted/30 px-3.5 py-2.5 text-sm leading-relaxed text-muted-foreground"
                  >
                    {item.text}
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          {parsed.takeaways.length > 0 ? (
            <Section icon={<CheckCircle2 className="h-3.5 w-3.5" />} title="可执行结论" count={parsed.takeaways.length}>
              <ol className="space-y-2">
                {parsed.takeaways.map((item, index) => (
                  <li
                    key={index}
                    className="flex gap-3 rounded-2xl border border-border/60 bg-gradient-to-br from-card to-[hsl(var(--success)/0.06)] px-3 py-2.5 shadow-soft"
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[hsl(var(--success)/0.15)] text-[11px] font-semibold text-[hsl(var(--success))]">
                      {index + 1}
                    </span>
                    <p className="min-w-0 flex-1 text-sm leading-relaxed text-foreground">{item}</p>
                  </li>
                ))}
              </ol>
            </Section>
          ) : null}

          {!parsed.theme &&
          parsed.concepts.length === 0 &&
          parsed.points.length === 0 &&
          parsed.evidence.length === 0 &&
          parsed.takeaways.length === 0 &&
          parsed.rawMarkdown ? (
            <pre className="whitespace-pre-wrap rounded-2xl border border-border/60 bg-muted/40 p-3 text-xs leading-5 text-foreground shadow-soft">
              {parsed.rawMarkdown}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}
