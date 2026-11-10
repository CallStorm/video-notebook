import { useMemo, useRef, useState } from "react";
import { Download, Maximize2, Minimize2, Play, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { parseClockToSeconds } from "@/components/studio-notes";
import {
  parseReadingPage,
  type ReadingCallout,
  type ReadingCard,
  type ReadingDiagram,
  type ReadingSection,
  type ReadingStep,
  type SequenceRow,
} from "@/studio/plugins/reading_page/parse";

export interface ReadingSource {
  id: number;
  title: string;
}

const PAPER_STYLE = `
.reading-page {
  background: #f7f4ef;
  color: #1c1917;
  font-family: "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC", "Source Han Sans SC", "Microsoft YaHei", "WenQuanYi Micro Hei", sans-serif;
}
.reading-page .reading-serif {
  font-family: "Noto Serif CJK SC", "Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", "SimSun", serif;
}
.reading-page article { container-type: inline-size; }
.reading-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 20px;
}
@container (min-width: 34rem) {
  .reading-cards { grid-template-columns: 1fr 1fr; }
}
`;

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
      return count + section.steps.filter((step) => step.time && seekVideoId(step, videos) != null).length;
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
    ? "reading-page fixed inset-0 z-40 flex flex-col"
    : "reading-page flex min-h-0 flex-1 flex-col";

  return (
    <div className={shell}>
      <style>{PAPER_STYLE}</style>
      <div className="flex h-[52px] shrink-0 items-center justify-between gap-3 border-b border-[#e8e2d9] bg-[#fbf9f6] px-5 sm:px-[22px]">
        <p className="min-w-0 truncate text-[13px] text-[#78716c]">
          <button type="button" className="hover:text-[#1c1917] hover:underline" onClick={onBack}>
            产物
          </button>
          <span className="px-1.5">›</span>
          <span className="font-medium text-[#44403c]">{crumb}</span>
        </p>
        <div className="flex shrink-0 items-center">
          {text ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-[#44403c] hover:bg-[#efeae3] hover:text-[#1c1917]"
              title="下载"
              onClick={download}
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
          ) : null}
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-[#44403c] hover:bg-[#efeae3] hover:text-[#1c1917]"
            title={expanded ? "还原" : "铺满"}
            onClick={onToggleExpanded}
          >
            {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
          <button
            type="button"
            title="关闭"
            className="rounded-full p-1.5 text-[#78716c] hover:bg-[#efeae3] hover:text-[#1c1917]"
            onClick={onBack}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {notice ? (
        <p className={`px-6 py-8 text-sm ${noticeError ? "text-[#9a3412]" : "text-[#78716c]"}`}>{notice}</p>
      ) : !page ? (
        <p className="px-6 py-8 text-sm text-[#78716c]">阅读页内容无法解析</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <article className="mx-auto w-[min(44rem,calc(100%-3rem))] pb-20 pt-12">
            {page.kicker ? (
              <p className="text-xs font-semibold tracking-[0.16em] text-[#0f766e]">{page.kicker}</p>
            ) : null}
            <h1
              className={`reading-serif text-[2rem] font-bold leading-[1.3] tracking-[-0.02em] text-[#1c1917] ${page.kicker ? "mt-2.5" : ""}`}
            >
              {docTitle}
            </h1>
            {sourceCount > 0 || seekableCount > 0 ? (
              <div className="relative mt-[18px] flex flex-wrap gap-2">
                {sourceCount > 0 ? (
                  <button
                    type="button"
                    className="inline-flex h-7 items-center rounded-full border border-[#e8e2d9] bg-[#fffcf8] px-[11px] text-xs text-[#44403c] hover:border-[#0f766e55]"
                    onClick={() => setSourcesOpen((open) => !open)}
                  >
                    {sourceCount === 1 ? "1 个来源" : `${sourceCount} 个来源`}
                  </button>
                ) : null}
                {seekableCount > 0 ? (
                  <span className="inline-flex h-7 items-center rounded-full border border-[#e8e2d9] bg-[#fffcf8] px-[11px] text-xs text-[#44403c]">
                    {seekableCount === 1 ? "1 处可跳转原片" : `${seekableCount} 处可跳转原片`}
                  </span>
                ) : null}
                {sourcesOpen && sourceCount > 0 ? (
                  <div className="absolute left-0 top-full z-10 mt-2 w-64 overflow-hidden rounded-xl border border-[#e8e2d9] bg-[#fffcf8] py-1 text-[#1c1917] shadow-[0_8px_24px_-12px_rgba(28,25,23,0.28)]">
                    {videos.map((video) => (
                      <button
                        key={`video-${video.id}`}
                        type="button"
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-[#f3eee6]"
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
                        className="block w-full truncate px-3 py-2 text-left text-sm hover:bg-[#f3eee6]"
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
              <aside className="mt-7 rounded-r-xl border-l-4 border-[#0f766e] bg-[linear-gradient(90deg,#0f766e14,transparent_92%)] px-5 py-4">
                <p className="text-[11px] font-bold tracking-[0.12em] text-[#0f766e]">主题</p>
                <p className="mt-1.5 text-base font-medium leading-[1.7] text-[#1c1917]">{page.theme}</p>
              </aside>
            ) : null}

            {page.lede ? <p className="mt-[22px] text-base leading-[1.8] text-[#44403c]">{page.lede}</p> : null}

            {page.sections.length > 1 ? (
              <nav aria-label="目录" className="mt-8">
                <p className="text-[11px] font-bold tracking-[0.12em] text-[#78716c]">目录</p>
                <ol className="mt-2.5 list-none border-l border-[#e8e2d9] pl-[18px]">
                  {page.sections.map((section, index) => (
                    <li key={section.id} className="mb-2 text-sm leading-normal text-[#44403c]">
                      <button
                        type="button"
                        className="text-left hover:text-[#0f766e]"
                        onClick={() => scrollToSection(section.id)}
                      >
                        <span className="mr-1 inline-block w-[1.6rem] font-mono text-xs text-[#78716c]">
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
              <ReadingSectionView
                key={section.id}
                section={section}
                index={sectionIndex}
                videos={videos}
                onJump={jump}
                sectionRef={(node) => {
                  sectionRefs.current[section.id] = node;
                }}
              />
            ))}

            {page.closing ? (
              <section className="mt-[52px] border-t border-[#e8e2d9] pt-6">
                <h2 className="reading-serif text-[1.15rem] font-bold leading-snug text-[#1c1917]">收束</h2>
                <p className="mt-4 text-[15.5px] leading-[1.85] text-[#1c1917]">{page.closing}</p>
              </section>
            ) : null}
          </article>
        </div>
      )}
    </div>
  );
}

function ReadingSectionView({
  section,
  index,
  videos,
  onJump,
  sectionRef,
}: {
  section: ReadingSection;
  index: number;
  videos: ReadingSource[];
  onJump: (step: ReadingStep) => void;
  sectionRef: (node: HTMLElement | null) => void;
}) {
  return (
    <section
      id={section.id}
      ref={sectionRef}
      className="mt-12 scroll-mt-6"
    >
      <h2 className="reading-serif text-[1.35rem] font-bold leading-[1.4] text-[#1c1917]">
        <span className="mr-2 font-mono text-[13px] font-semibold text-[#0f766e]">
          {String(index + 1).padStart(2, "0")}
        </span>
        {section.title}
      </h2>
      {section.summary ? <p className="mt-2 text-sm leading-[1.7] text-[#78716c]">{section.summary}</p> : null}
      {section.prose.map((paragraph, paragraphIndex) => (
        <p key={`${section.id}-prose-${paragraphIndex}`} className="mt-4 text-[15.5px] leading-[1.85] text-[#1c1917]">
          {paragraph}
        </p>
      ))}
      {section.diagram ? <ReadingDiagramView diagram={section.diagram} /> : null}
      {section.steps.length > 0 ? (
        <div className="mt-[22px] flex flex-col gap-3.5">
          {section.steps.map((step, stepIndex) => (
            <StepCard
              key={`${section.id}-step-${stepIndex}`}
              step={step}
              number={stepIndex + 1}
              canSeek={step.time != null && seekVideoId(step, videos) != null}
              onJump={() => onJump(step)}
            />
          ))}
        </div>
      ) : null}
      {section.cards.length > 0 ? <PropertyCards cards={section.cards} /> : null}
      {section.callout ? <CalloutView callout={section.callout} /> : null}
    </section>
  );
}

function StepCard({
  step,
  number,
  canSeek,
  onJump,
}: {
  step: ReadingStep;
  number: number;
  canSeek: boolean;
  onJump: () => void;
}) {
  const showTitle = Boolean(step.title && step.title !== step.body);
  return (
    <div className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 rounded-2xl border border-[#e8e2d9] bg-[#fffcf8] py-4 pl-3.5 pr-4">
      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-[13px] font-bold text-white">
        {number}
      </div>
      <div className="min-w-0">
        {showTitle ? <h3 className="mt-0.5 text-[15.5px] font-bold leading-snug text-[#1c1917]">{step.title}</h3> : null}
        <p className={`${showTitle ? "mt-1.5" : "mt-0.5"} text-[14.5px] leading-[1.75] text-[#44403c]`}>{step.body}</p>
        {step.quote ? (
          <blockquote className="mt-2.5 border-l-2 border-[#0f766e73] pl-3 text-[13.5px] italic leading-[1.7] text-[#78716c]">
            {step.quote}
          </blockquote>
        ) : null}
        {step.aside ? <p className="mt-2 text-sm leading-6 text-[#78716c]">{step.aside}</p> : null}
        {step.time ? (
          canSeek ? (
            <button
              type="button"
              className="mt-2.5 inline-flex items-center gap-[5px] font-mono text-xs text-[#0f766e] hover:underline"
              title="跳到原片"
              onClick={onJump}
            >
              <Play className="h-3 w-3 fill-current" />
              {step.time} 跳到原片
            </button>
          ) : (
            <span className="mt-2.5 inline-flex items-center gap-[5px] font-mono text-xs text-[#78716c]">{step.time}</span>
          )
        ) : null}
      </div>
    </div>
  );
}

function CalloutView({ callout }: { callout: ReadingCallout }) {
  const warn = callout.tone === "warn";
  return (
    <aside
      className={`mt-5 rounded-xl px-4 py-3.5 ${
        warn ? "border border-[#9a341233] bg-[#9a341214]" : "border border-[#0f766e2a] bg-[#0f766e14]"
      }`}
    >
      <p className={`text-xs font-bold tracking-[0.08em] ${warn ? "text-[#9a3412]" : "text-[#0f766e]"}`}>
        {callout.label || (warn ? "注意" : "要点")}
      </p>
      <p className="mt-1.5 text-[14.5px] leading-[1.7] text-[#1c1917]">{callout.body}</p>
    </aside>
  );
}

function PropertyCards({ cards }: { cards: ReadingCard[] }) {
  return (
    <div className="reading-cards">
      {cards.map((card, index) => (
        <div key={`${card.title}-${index}`} className="rounded-[14px] border border-[#e8e2d9] bg-[#fffcf8] px-3.5 pb-[13px] pt-3.5">
          <div className="text-xs font-bold text-[#0f766e]">{card.title}</div>
          <p className="mt-1.5 text-[13.5px] leading-[1.65] text-[#44403c]">{card.body}</p>
        </div>
      ))}
    </div>
  );
}

function ReadingDiagramView({ diagram }: { diagram: ReadingDiagram }) {
  if (diagram.kind === "compare") return <CompareTable diagram={diagram} />;
  if (diagram.kind === "sequence") return <SequenceDiagram diagram={diagram} />;
  return <FlowDiagram diagram={diagram} />;
}

function DiagramCaption({ caption }: { caption?: string }) {
  if (!caption) return null;
  return <figcaption className="mt-2 text-center text-xs text-[#78716c]">{caption}</figcaption>;
}

function FlowDiagram({ diagram }: { diagram: ReadingDiagram }) {
  return (
    <figure className="mt-[22px]">
      <div className="overflow-x-auto rounded-2xl border border-[#e8e2d9] bg-[#fffcf8] px-4 py-[18px]">
        <div
          className="grid w-max min-w-full items-stretch"
          style={{
            gridTemplateColumns: diagram.nodes
              .map((_, index) => (index === 0 ? "minmax(7.25rem,1fr)" : "1.75rem minmax(7.25rem,1fr)"))
              .join(" "),
          }}
        >
          {diagram.nodes.map((node, index) => (
            <div key={`${node.label}-${index}`} className="contents">
              {index > 0 ? (
                <div className="flex items-center justify-center text-lg text-[#0f766e]" aria-hidden>
                  →
                </div>
              ) : null}
              <div className="flex flex-col justify-center rounded-xl border border-[#0f766e2a] bg-[#f3faf8] px-2.5 py-3 text-center">
                <strong className="block text-[13.5px] font-bold leading-snug text-[#1c1917]">{node.label}</strong>
                {node.detail ? (
                  <span className="mt-1 block text-[11.5px] leading-snug text-[#78716c]">{node.detail}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
      <DiagramCaption caption={diagram.caption} />
    </figure>
  );
}

function CompareTable({ diagram }: { diagram: ReadingDiagram }) {
  const columns = diagram.columns ?? ["对照", "说明"];
  const contrast = diagram.tone === "contrast";
  return (
    <figure className="mt-5">
      <div className="overflow-hidden rounded-[14px] border border-[#e8e2d9] bg-[#fffcf8]">
        <table className="w-full border-separate border-spacing-0">
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  className="bg-[#f3eee6] px-3.5 py-[11px] text-left text-xs tracking-[0.06em] text-[#44403c] [&+th]:border-l [&+th]:border-[#e8e2d9]"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {diagram.nodes.map((node, index) => (
              <tr key={`${node.label}-${index}`}>
                <td
                  className={`border-t border-[#e8e2d9] px-3.5 py-[11px] align-top text-[13.5px] leading-[1.65] ${
                    contrast ? "text-[#9a3412]" : "text-[#1c1917]"
                  }`}
                >
                  {node.label}
                </td>
                <td
                  className={`border-l border-t border-[#e8e2d9] px-3.5 py-[11px] align-top text-[13.5px] leading-[1.65] ${
                    contrast ? "text-[#166534]" : "text-[#44403c]"
                  }`}
                >
                  {node.detail || ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <DiagramCaption caption={diagram.caption} />
    </figure>
  );
}

function SequenceDiagram({ diagram }: { diagram: ReadingDiagram }) {
  const rich = diagram.lanes && diagram.lanes.length >= 2 && diagram.rows && diagram.rows.length >= 2;
  if (rich && diagram.lanes && diagram.rows) {
    return (
      <SequenceChart
        lanes={diagram.lanes}
        rows={diagram.rows}
        rowHeader={diagram.rowHeader || "节奏"}
        caption={diagram.caption}
      />
    );
  }
  return (
    <figure className="mt-5">
      <div className="overflow-x-auto rounded-2xl border border-[#e8e2d9] bg-[#fffcf8] px-4 py-4">
        <ol className="flex w-max min-w-full items-stretch">
          {diagram.nodes.map((node, index) => (
            <li key={`${node.label}-${index}`} className="flex min-w-[8.5rem] flex-1 items-stretch">
              {index > 0 ? (
                <span className="flex w-7 shrink-0 items-center justify-center text-[#0f766e]" aria-hidden>
                  →
                </span>
              ) : null}
              <span className="flex flex-1 flex-col justify-center rounded-xl border border-[#0f766e2a] bg-[#f3faf8] px-3 py-2.5 text-center">
                <span className="font-mono text-xs font-semibold text-[#0f766e]">{index + 1}</span>
                <span className="mt-1 block text-sm font-semibold leading-snug text-[#1c1917]">{node.label}</span>
                {node.detail ? (
                  <span className="mt-1 block text-[11.5px] leading-snug text-[#78716c]">{node.detail}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      </div>
      <DiagramCaption caption={diagram.caption} />
    </figure>
  );
}

function SequenceChart({
  lanes,
  rows,
  rowHeader,
  caption,
}: {
  lanes: string[];
  rows: SequenceRow[];
  rowHeader: string;
  caption?: string;
}) {
  return (
    <figure className="mt-5">
      <div className="overflow-x-auto rounded-2xl border border-[#e8e2d9] bg-[#fffcf8] px-4 pb-2 pt-4">
        <div
          className="grid w-max min-w-full items-center gap-x-2 gap-y-1"
          style={{ gridTemplateColumns: `5.2rem repeat(${lanes.length}, minmax(6.5rem, 1fr))` }}
        >
          <span className="text-xs font-medium text-[#78716c]">{rowHeader}</span>
          {lanes.map((lane) => (
            <span key={lane} className="text-center text-xs font-bold text-[#44403c]">
              {lane}
            </span>
          ))}
          {rows.map((row, rowIndex) => (
            <SequenceRowCells key={`${row.label}-${rowIndex}`} row={row} lanes={lanes} />
          ))}
        </div>
      </div>
      <DiagramCaption caption={caption} />
    </figure>
  );
}

function SequenceRowCells({ row, lanes }: { row: SequenceRow; lanes: string[] }) {
  return (
    <>
      <span className="self-center font-mono text-[11px] text-[#78716c]">{row.label}</span>
      {lanes.map((lane) => {
        const cell = row.cells.find((item) => item.lane === lane);
        return (
          <span key={lane} className="flex min-h-11 items-center justify-center">
            {cell ? (
              <span className="rounded-lg bg-[#0f766e14] px-2 py-[5px] text-center text-[11.5px] leading-[1.4] text-[#1c1917]">
                {cell.text}
              </span>
            ) : null}
          </span>
        );
      })}
    </>
  );
}

export { StudioReadingPage as ResultView };
