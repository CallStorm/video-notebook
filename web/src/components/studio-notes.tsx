import { useMemo, useState } from "react";
import { Download, Maximize2, Minimize2, X } from "lucide-react";
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
        const time = typeof row.time === "string" ? row.time.trim() : undefined;
        points.push(time ? { time, text: textValue } : { text: textValue });
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
    const m = /^`?(\d{1,2}:\d{2}(?::\d{2})?)`?\s+(.+)$/.exec(cleaned);
    if (m) points.push({ time: m[1], text: m[2].trim() });
    else if (cleaned) points.push({ text: cleaned });
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
}) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const parsed = useMemo(() => parseNotes(text), [text]);
  const sourceCount = videos.length + notes.length;
  const primaryVideoId = videos[0]?.id;

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

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
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
              {sourceCount === 1 ? "1 个来源" : `${sourceCount} 个来源`}
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
      ) : !parsed ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">暂无内容</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-8">
          {parsed.theme ? (
            <section className="mb-5">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">主题</p>
              <p className="mt-1.5 text-sm leading-relaxed text-foreground">{parsed.theme}</p>
            </section>
          ) : null}

          {parsed.concepts.length > 0 ? (
            <section className="mb-5">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">关键概念</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {parsed.concepts.map((concept, index) => (
                  <div
                    key={`${concept.term}-${index}`}
                    className="max-w-full rounded-2xl border border-border/70 bg-muted/40 px-3 py-2"
                  >
                    <div className="text-sm font-semibold text-foreground">{concept.term}</div>
                    {concept.definition ? (
                      <div className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{concept.definition}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {parsed.points.length > 0 ? (
            <section className="mb-5">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">要点</p>
              <ul className="mt-2 space-y-2">
                {parsed.points.map((point, index) => (
                  <li
                    key={`${point.time ?? ""}-${index}`}
                    className="flex gap-3 rounded-xl border border-border/60 bg-background/60 px-3 py-2.5"
                  >
                    {point.time ? (
                      <button
                        type="button"
                        className="mt-0.5 shrink-0 rounded-md bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-primary hover:bg-primary/15 disabled:opacity-60"
                        disabled={primaryVideoId == null}
                        title={primaryVideoId == null ? point.time : "打开来源（精确跳转时间轴后续支持）"}
                        onClick={() => {
                          if (primaryVideoId != null) onOpenVideo(primaryVideoId);
                        }}
                      >
                        {point.time}
                      </button>
                    ) : null}
                    <p className="min-w-0 flex-1 text-sm leading-relaxed text-foreground">{point.text}</p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {parsed.evidence.length > 0 ? (
            <section className="mb-5">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">论据 / 原文要点</p>
              <ul className="mt-2 space-y-2">
                {parsed.evidence.map((item, index) => (
                  <li
                    key={index}
                    className="rounded-xl border-l-2 border-primary/30 bg-muted/30 px-3 py-2 text-sm leading-relaxed text-muted-foreground"
                  >
                    {item.text}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {parsed.takeaways.length > 0 ? (
            <section className="mb-2">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">可执行结论</p>
              <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-foreground">
                {parsed.takeaways.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ol>
            </section>
          ) : null}

          {!parsed.theme &&
          parsed.concepts.length === 0 &&
          parsed.points.length === 0 &&
          parsed.evidence.length === 0 &&
          parsed.takeaways.length === 0 &&
          parsed.rawMarkdown ? (
            <pre className="whitespace-pre-wrap rounded-xl bg-muted/40 p-3 text-xs leading-5 text-foreground">
              {parsed.rawMarkdown}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
}
