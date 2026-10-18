import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { init } from "pptx-preview";
import { Download, Maximize2, Minimize2, Play, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export interface SlideArtifact {
  id: number;
  role: string;
  filename: string;
  mime: string;
}

export interface SlideSource {
  id: number;
  title: string;
}

const SLIDE_WIDTH = 960;
const SLIDE_HEIGHT = 540;
const SCROLL_GAP = 16;

export function StudioSlides({
  access,
  taskId,
  title,
  crumb,
  artifacts,
  pending,
  notice,
  videos,
  notes,
  expanded,
  onBack,
  onToggleExpanded,
  onOpenVideo,
  onOpenNote,
}: {
  access: string;
  taskId: number;
  title: string;
  crumb: string;
  artifacts: SlideArtifact[];
  pending?: boolean;
  notice?: string | null;
  videos: SlideSource[];
  notes: SlideSource[];
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
  onOpenVideo: (videoId: number) => void;
  onOpenNote: (noteId: number) => void;
}) {
  const main = artifacts.find((item) => item.role === "main") ?? null;
  const pptx = useSignedArtifact(access, taskId, main?.id ?? null);
  const stageRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const presentRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [count, setCount] = useState(0);
  const [presenting, setPresenting] = useState(false);
  const [failed, setFailed] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const sourceCount = videos.length + notes.length;
  const mode = presenting ? "present" : expanded ? "expand" : "scroll";
  const shell =
    expanded || presenting
      ? "fixed inset-0 z-40 flex flex-col bg-background"
      : "flex min-h-0 flex-1 flex-col bg-background";

  useEffect(() => {
    const host = hostRef.current;
    const url = pptx.data?.url;
    if (!host || !url) return;
    let cancelled = false;
    setFailed(false);
    setIndex(0);
    setCount(0);
    const previewer = init(host, { width: SLIDE_WIDTH, height: SLIDE_HEIGHT, mode: "list" });
    void (async () => {
      const response = await fetch(url);
      if (!response.ok) throw new Error("load failed");
      const buffer = await response.arrayBuffer();
      if (cancelled) return;
      await previewer.preview(buffer);
      if (cancelled) return;
      const wrapper = host.querySelector(".pptx-preview-wrapper");
      if (wrapper instanceof HTMLElement) {
        wrapper.style.overflow = "visible";
        wrapper.style.background = "transparent";
        wrapper.style.margin = "0";
        wrapper.style.width = `${SLIDE_WIDTH}px`;
      }
      host.querySelectorAll(".pptx-preview-wrapper-pagination, .pptx-preview-wrapper-next").forEach((node) => {
        if (node instanceof HTMLElement) node.style.display = "none";
      });
      setCount(slideNodes(host).length);
    })().catch(() => {
      if (!cancelled) setFailed(true);
    });
    return () => {
      cancelled = true;
      previewer.destroy();
      host.replaceChildren();
      railRef.current?.replaceChildren();
    };
  }, [pptx.data?.url]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || count === 0) return;
    applyMode(host, mode, index);
    if (mode === "expand") {
      mountThumbs(railRef.current, slideNodes(host), index);
    } else {
      railRef.current?.replaceChildren();
    }
  }, [index, count, mode]);

  useEffect(() => {
    const stage = stageRef.current;
    const frame = frameRef.current;
    const host = hostRef.current;
    if (!stage || !frame || !host || count === 0) return;
    const fit = () => fitHost(stage, frame, host, mode, count);
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(stage);
    return () => observer.disconnect();
  }, [count, mode]);

  useEffect(() => {
    if (!presenting) return;
    const node = presentRef.current;
    if (!node) return;
    void node.requestFullscreen?.().catch(() => {
      setPresenting(false);
    });
    const onChange = () => {
      if (document.fullscreenElement !== node) setPresenting(false);
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => {
      document.removeEventListener("fullscreenchange", onChange);
      if (document.fullscreenElement === node) void document.exitFullscreen?.();
    };
  }, [presenting]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (count < 1) return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if (event.key === "Escape" && presenting) {
        setPresenting(false);
        return;
      }
      if (mode === "scroll") return;
      if (event.key === "ArrowRight" || event.key === " ") {
        event.preventDefault();
        advance(1);
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        advance(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function advance(delta: number) {
    if (delta > 0 && index >= count - 1) {
      if (presenting) setPresenting(false);
      return;
    }
    setIndex((current) => Math.min(count - 1, Math.max(0, current + delta)));
  }

  function startPresent() {
    setIndex(0);
    setPresenting(true);
  }

  const pptxName = main?.filename || `${title}.pptx`;

  return (
    <div ref={presentRef} className={presenting ? `${shell} bg-black` : shell}>
      {presenting ? null : (
        <>
          <div className="flex items-center justify-between px-5 pt-4">
            <p className="min-w-0 truncate text-sm text-muted-foreground">
              <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
                Studio
              </button>
              <span className="px-1.5">›</span>
              <span className="text-foreground">{crumb}</span>
            </p>
            <div className="flex shrink-0 items-center gap-1">
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                title="播放"
                disabled={count < 1}
                onClick={startPresent}
              >
                <Play className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                title={expanded ? "还原" : "铺满"}
                onClick={onToggleExpanded}
              >
                {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
              {pptx.data?.url ? (
                <a
                  href={pptx.data.url}
                  download={pptxName}
                  title="下载"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
                >
                  <Download className="h-4 w-4" />
                </a>
              ) : (
                <Button size="icon" variant="ghost" className="h-8 w-8" title="下载" disabled>
                  <Download className="h-4 w-4" />
                </Button>
              )}
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
        </>
      )}
      {notice ? (
        <p className="px-5 py-4 text-sm text-destructive">{notice}</p>
      ) : pending || (pptx.isLoading && main) ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">加载预览…</p>
      ) : failed || !main ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">预览不可用</p>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div
            ref={stageRef}
            className={
              mode === "scroll"
                ? "min-h-0 min-w-0 flex-1 overflow-y-auto px-5 pb-6"
                : "relative min-h-0 min-w-0 flex-1 overflow-hidden"
            }
            onClick={presenting ? () => advance(1) : undefined}
          >
            <div ref={frameRef} className={mode === "scroll" ? "relative mx-auto" : "absolute inset-0"}>
              <div
                ref={hostRef}
                className={mode === "scroll" ? "absolute left-1/2 top-0" : "absolute left-1/2 top-1/2"}
              />
            </div>
            {count === 0 ? (
              <p className="px-1 pt-2 text-sm text-muted-foreground">加载预览…</p>
            ) : null}
          </div>
          {mode === "expand" ? (
            <div
              ref={railRef}
              className="flex w-40 shrink-0 flex-col gap-2 overflow-y-auto border-l p-3"
              onClick={(event) => {
                if (!(event.target instanceof Element)) return;
                const button = event.target.closest("button[data-index]");
                if (!(button instanceof HTMLElement) || button.dataset.index == null) return;
                setIndex(Number(button.dataset.index));
              }}
            />
          ) : (
            <div ref={railRef} className="hidden" />
          )}
        </div>
      )}
    </div>
  );
}

function slideNodes(host: HTMLElement): HTMLElement[] {
  return [...host.querySelectorAll(".pptx-preview-slide-wrapper")].filter(
    (node): node is HTMLElement => node instanceof HTMLElement,
  );
}

function applyMode(host: HTMLElement, mode: "scroll" | "expand" | "present", index: number) {
  const slides = slideNodes(host);
  slides.forEach((slide, slideIndex) => {
    if (mode === "scroll") {
      slide.style.display = "block";
      slide.style.margin = `0 0 ${SCROLL_GAP}px`;
    } else {
      slide.style.display = slideIndex === index ? "block" : "none";
      slide.style.margin = "0";
    }
  });
}

function fitHost(
  stage: HTMLElement,
  frame: HTMLElement,
  host: HTMLElement,
  mode: "scroll" | "expand" | "present",
  count: number,
) {
  const slide = host.querySelector(".pptx-preview-slide-wrapper");
  const width = slide instanceof HTMLElement && slide.offsetWidth > 0 ? slide.offsetWidth : SLIDE_WIDTH;
  const height = slide instanceof HTMLElement && slide.offsetHeight > 0 ? slide.offsetHeight : SLIDE_HEIGHT;
  if (mode === "scroll") {
    const available = Math.max(240, stage.clientWidth - 8);
    const scale = Math.min(1, available / width);
    const contentHeight = count * height + Math.max(0, count - 1) * SCROLL_GAP;
    frame.style.width = `${width * scale}px`;
    frame.style.height = `${contentHeight * scale}px`;
    host.style.width = `${width}px`;
    host.style.height = `${contentHeight}px`;
    host.style.transform = `translateX(-50%) scale(${scale})`;
    host.style.transformOrigin = "top center";
    return;
  }
  frame.style.width = "100%";
  frame.style.height = "100%";
  const rect = stage.getBoundingClientRect();
  const scale = Math.min(rect.width / width, rect.height / height);
  host.style.width = `${width}px`;
  host.style.height = `${height}px`;
  host.style.transform = `translate(-50%, -50%) scale(${Number.isFinite(scale) && scale > 0 ? scale : 1})`;
  host.style.transformOrigin = "center center";
}

function mountThumbs(rail: HTMLDivElement | null, slides: HTMLElement[], active: number) {
  if (!rail) return;
  rail.replaceChildren();
  const thumbWidth = 128;
  const sample = slides[0];
  const width = sample?.offsetWidth || SLIDE_WIDTH;
  const height = sample?.offsetHeight || SLIDE_HEIGHT;
  const scale = thumbWidth / width;
  slides.forEach((slide, slideIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.index = String(slideIndex);
    button.title = `第 ${slideIndex + 1} 页`;
    button.className = "shrink-0 overflow-hidden rounded-md bg-muted";
    button.style.width = `${thumbWidth}px`;
    button.style.height = `${Math.round(height * scale)}px`;
    button.style.outline = slideIndex === active ? "2px solid #1e3a8a" : "1px solid transparent";
    const clone = slide.cloneNode(true);
    if (clone instanceof HTMLElement) {
      clone.style.display = "block";
      clone.style.margin = "0";
      clone.style.transform = `scale(${scale})`;
      clone.style.transformOrigin = "top left";
      clone.style.pointerEvents = "none";
      button.append(clone);
    }
    rail.append(button);
  });
}

function useSignedArtifact(access: string, taskId: number, artifactId: number | null) {
  return useQuery({
    queryKey: ["studio-artifact-url", taskId, artifactId],
    queryFn: () =>
      api<{ url: string; expires_in: number }>(`/studio/tasks/${taskId}/artifacts/${artifactId}`, { access }),
    enabled: !!access && artifactId != null,
  });
}
