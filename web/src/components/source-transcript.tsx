import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, Sparkles } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface SubtitleLine {
  line_no: number;
  start_ms: number;
  end_ms: number;
  text: string;
}

interface SubtitleView {
  video_id: number;
  subtitle_status: "pending" | "processing" | "ready" | "failed";
  subtitle_error: string | null;
  source: string | null;
  language: string | null;
  line_count: number;
  lines: SubtitleLine[];
}

interface PlayUrl {
  url: string;
  expires_in: number;
}

async function fetchSubtitle(access: string, videoId: number): Promise<SubtitleView> {
  return api<SubtitleView>(`/sources/${videoId}/subtitle`, { access });
}

async function fetchPlayUrl(access: string, videoId: number): Promise<PlayUrl> {
  return api<PlayUrl>(`/sources/${videoId}/play_url`, { access });
}

function fmtClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtSrtClock(ms: number): string {
  const clamped = Math.max(0, ms);
  const hours = Math.floor(clamped / 3_600_000);
  const minutes = Math.floor((clamped % 3_600_000) / 60_000);
  const seconds = Math.floor((clamped % 60_000) / 1000);
  const millis = clamped % 1000;
  const pad = (n: number, w = 2) => n.toString().padStart(w, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)},${pad(millis, 3)}`;
}

function downloadSrt(title: string, lines: SubtitleLine[]) {
  const body = lines
    .map(
      (line, index) =>
        `${index + 1}\n${fmtSrtClock(line.start_ms)} --> ${fmtSrtClock(line.end_ms)}\n${line.text}\n`,
    )
    .join("\n");
  const blob = new Blob([body], { type: "application/x-subrip" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${title || "subtitle"}.srt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function SourceTranscript({
  access,
  videoId,
  title,
  hasFile,
  overviewStatus,
  overviewText,
  overviewError,
  focusLineNo,
  seekTimeSec,
  seekNonce,
  onBack,
}: {
  access: string;
  videoId: number;
  title: string;
  hasFile: boolean;
  overviewStatus: "pending" | "processing" | "ready" | "failed";
  overviewText: string | null;
  overviewError: string | null;
  focusLineNo?: number | null;
  /** Absolute seek target in seconds; changes trigger player seek+play. */
  seekTimeSec?: number | null;
  /** Bumps when the same timestamp is requested again. */
  seekNonce?: number | null;
  onBack: () => void;
}) {
  const [guideOpen, setGuideOpen] = useState(true);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const subtitle = useQuery({
    queryKey: ["subtitle", videoId],
    queryFn: () => fetchSubtitle(access, videoId),
    enabled: !!access && !!videoId,
    refetchInterval: (query) => {
      const status = query.state.data?.subtitle_status;
      return status === "pending" || status === "processing" ? 2000 : false;
    },
  });
  const play = useQuery({
    queryKey: ["play", videoId],
    queryFn: () => fetchPlayUrl(access, videoId),
    enabled: !!access && !!videoId && hasFile,
  });

  const view = subtitle.data;
  const status = view?.subtitle_status;
  const lines = view?.lines ?? [];
  const busy = status === "pending" || status === "processing";
  const errorText =
    view?.subtitle_error ||
    (subtitle.error instanceof ApiError ? subtitle.error.message : null);

  useEffect(() => {
    if (focusLineNo == null || lines.length === 0) return;
    document.getElementById(`cue-${focusLineNo}`)?.scrollIntoView({ block: "center" });
  }, [focusLineNo, lines.length, videoId]);

  useEffect(() => {
    if (seekTimeSec == null || Number.isNaN(seekTimeSec)) return;
    const video = videoRef.current;
    if (!video) return;
    const token = seekTimeSec;
    const apply = () => {
      try {
        video.currentTime = Math.max(0, token);
        void video.play().catch(() => {});
      } catch {
        /* ignore seek races while metadata loads */
      }
    };
    if (video.readyState >= 1) apply();
    else {
      const onReady = () => apply();
      video.addEventListener("loadedmetadata", onReady, { once: true });
      return () => video.removeEventListener("loadedmetadata", onReady);
    }
  }, [seekTimeSec, seekNonce, videoId, play.data?.url]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden px-3 py-3">
      <div className="flex shrink-0 items-start gap-1">
        <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={onBack} title="返回来源列表">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h3 className="min-w-0 flex-1 pt-1 text-sm font-medium leading-5">{title}</h3>
      </div>

      <section
        className={`rounded-2xl border border-border/60 bg-gradient-to-br from-card to-accent/30 shadow-soft ${guideOpen ? "flex min-h-0 flex-1 flex-col overflow-hidden" : "shrink-0"}`}
      >
        <button
          type="button"
          className="flex w-full shrink-0 items-center gap-2 px-3 py-2.5 text-left"
          onClick={() => setGuideOpen((open) => !open)}
        >
          <Sparkles className="h-4 w-4 shrink-0 text-[hsl(var(--success))]" />
          <span className="flex-1 text-sm font-medium">概览</span>
          <ChevronDown className={`h-4 w-4 text-muted-foreground transition ${guideOpen ? "" : "-rotate-90"}`} />
        </button>
        {guideOpen ? (
          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 text-xs leading-5 text-muted-foreground">
            {overviewStatus === "processing" ? (
              <p>正在生成概览…</p>
            ) : overviewStatus === "ready" && overviewText ? (
              <p className="whitespace-pre-wrap text-foreground">{overviewText}</p>
            ) : overviewStatus === "failed" ? (
              <div className="rounded-xl border border-amber-200/80 bg-amber-50 px-3 py-2 text-amber-900">
                <p className="font-medium">概览生成失败</p>
                <p className="mt-0.5 opacity-90">{overviewError || "可在来源菜单里点「重新生成」再试。"}</p>
              </div>
            ) : (
              <p>还没有概览。字幕完成后通常会自动生成；也可在来源列表点「重新生成」重做字幕与概览。</p>
            )}
          </div>
        ) : null}
      </section>

      <section className="player-island">
        {hasFile && play.data?.url ? (
          <video
            key={play.data.url}
            ref={videoRef}
            className="aspect-video w-full bg-player accent-primary"
            controls
            playsInline
            preload="metadata"
            src={play.data.url}
          />
        ) : (
          <div className="flex aspect-video items-center justify-center px-4 text-center text-xs text-player-foreground/70">
            {!hasFile
              ? "视频还没保存到本地，暂时不能播放。"
              : play.isError
                ? "视频地址获取失败"
                : "正在准备播放…"}
          </div>
        )}
      </section>

      <section className="flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex shrink-0 items-center justify-between gap-2">
          <h4 className="text-sm font-semibold tracking-tight">字幕</h4>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-[11px]"
              disabled={lines.length === 0}
              onClick={() => downloadSrt(title, lines)}
            >
              下载 SRT
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {!hasFile ? (
            <p className="py-6 text-center text-xs text-muted-foreground">视频还没保存到本地，暂时无法生成字幕。</p>
          ) : null}
          {hasFile && busy && lines.length === 0 ? (
            <p className="py-6 text-center text-xs status-busy">正在生成字幕…</p>
          ) : null}
          {hasFile && busy && lines.length > 0 ? (
            <p className="mb-2 text-[11px] text-muted-foreground">正在重新生成，当前仍是上一版。</p>
          ) : null}
          {hasFile && !busy && lines.length === 0 ? (
            <div className="py-6 text-center text-xs text-muted-foreground">
              <p>暂无字幕</p>
              {errorText ? <p className="mt-2 text-destructive">{errorText}</p> : null}
            </div>
          ) : null}
          {hasFile && !busy && lines.length > 0 && errorText ? (
            <p className="mb-2 text-[11px] text-destructive">{errorText}</p>
          ) : null}
          {hasFile && lines.length > 0 ? (
            <div className="space-y-3 pb-6">
              {lines.map((line) => (
                <p
                  id={`cue-${line.line_no}`}
                  key={line.line_no}
                  className={`rounded-lg px-2 py-1 text-[13px] leading-6 transition-colors hover:bg-accent/40 ${
                    focusLineNo === line.line_no ? "bg-accent text-foreground ring-1 ring-primary/25" : ""
                  }`}
                >
                  <button
                    type="button"
                    className={`mr-2 rounded px-1 font-mono text-[10px] hover:bg-primary/10 hover:text-primary ${
                      focusLineNo === line.line_no ? "font-medium text-primary" : "text-muted-foreground"
                    }`}
                    title="跳转到此处"
                    onClick={() => {
                      const video = videoRef.current;
                      if (!video) return;
                      video.currentTime = Math.max(0, line.start_ms / 1000);
                      void video.play().catch(() => {});
                    }}
                  >
                    {fmtClock(line.start_ms)}
                  </button>
                  {line.text}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
