import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation } from "@tanstack/react-query";
import {
  ExternalLink,
  Loader2,
  MessageSquare,
  Play,
  Plus,
  Search as SearchIcon,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Platform = "youtube" | "bilibili" | "douyin";

interface SearchResultItem {
  id: string;
  title: string;
  url: string;
  thumbnail: string | null;
  platform: Platform;
  result_type: "video";
  duration: number | null;
  uploader: string | null;
  uploader_url: string | null;
  view_count: number | null;
  comment_count: number | null;
  description: string | null;
}

interface PlatformSearchError {
  platform: Platform;
  message: string;
}

interface SearchResponse {
  items: SearchResultItem[];
  errors: PlatformSearchError[];
}

interface PreviewResolveResponse {
  token: string;
  play_url: string;
  expires_in: number;
  title: string | null;
}

const PLATFORM_CHIPS: { id: "all" | Platform; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "bilibili", label: "B站" },
  { id: "youtube", label: "YouTube" },
];

const PLATFORM_BADGE: Record<
  Platform,
  { label: string; className: string; soft: string }
> = {
  youtube: {
    label: "YouTube",
    className: "bg-red-600 text-white",
    soft: "bg-red-50 text-red-700 ring-red-200/80",
  },
  bilibili: {
    label: "B站",
    className: "bg-[#FB7299] text-white",
    soft: "bg-pink-50 text-pink-700 ring-pink-200/80",
  },
  douyin: {
    label: "抖音",
    className: "bg-zinc-900 text-white",
    soft: "bg-zinc-100 text-zinc-800 ring-zinc-200/80",
  },
};

const PLATFORM_ERROR_LABEL: Record<Platform, string> = {
  bilibili: "B站",
  youtube: "YouTube",
  douyin: "抖音",
};

function formatDuration(sec: number | null): string | null {
  if (sec == null || sec < 0) return null;
  const s = Math.floor(sec % 60);
  const m = Math.floor((sec / 60) % 60);
  const h = Math.floor(sec / 3600);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Compact Chinese count: 1234 / 12.3万 / 1.2亿 */
function formatCount(n: number | null | undefined): string | null {
  if (n == null || Number.isNaN(n)) return null;
  if (n >= 100_000_000) {
    const v = n / 100_000_000;
    return `${v >= 10 ? v.toFixed(0) : v.toFixed(1)}亿`;
  }
  if (n >= 10_000) {
    const v = n / 10_000;
    return `${v >= 100 ? v.toFixed(0) : v.toFixed(1)}万`;
  }
  return String(n);
}

export interface NotebookWebSearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Add result URL into the current notebook (sources/fetch). */
  onAddUrl: (url: string) => void | Promise<unknown>;
  adding?: boolean;
}

export function NotebookWebSearchDialog({
  open,
  onOpenChange,
  onAddUrl,
  adding,
}: NotebookWebSearchDialogProps) {
  const { access } = useAuth();
  const token = access ?? "";
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState<"all" | Platform>("all");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [searchedQuery, setSearchedQuery] = useState("");
  const [preview, setPreview] = useState<SearchResultItem | null>(null);
  const [previewPlayUrl, setPreviewPlayUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [addingUrl, setAddingUrl] = useState<string | null>(null);
  const [addedUrls, setAddedUrls] = useState<Set<string>>(() => new Set());
  const [addError, setAddError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setPreview(null);
      setPreviewPlayUrl(null);
      setPreviewError(null);
      setAddingUrl(null);
      setAddError(null);
    }
  }, [open]);

  const search = useMutation({
    mutationFn: async () => {
      const platforms =
        platform === "all" ? undefined : ([platform] as Platform[]);
      return api<SearchResponse>("/search", {
        method: "POST",
        access: token,
        body: { query: query.trim(), platforms, limit_per_platform: 12 },
      });
    },
    onSuccess: (data) => {
      setResult(data);
      setSearchedQuery(query.trim());
      setAddError(null);
    },
  });

  const resolvePreview = useMutation({
    mutationFn: async (item: SearchResultItem) => {
      return api<PreviewResolveResponse>("/search/preview", {
        method: "POST",
        access: token,
        body: { url: item.url },
      });
    },
    onSuccess: (data) => {
      setPreviewPlayUrl(data.play_url);
      setPreviewError(null);
    },
    onError: (err) => {
      setPreviewPlayUrl(null);
      setPreviewError(
        err instanceof ApiError ? err.message : "预览解析失败，请重试",
      );
    },
  });

  if (!open) return null;

  const items = result?.items ?? [];
  const errors = result?.errors ?? [];
  const previewBusy = resolvePreview.isPending;
  const busyAdd = adding || !!addingUrl;

  const runSearch = () => {
    if (!query.trim() || search.isPending) return;
    search.mutate();
  };

  const openPreview = (item: SearchResultItem) => {
    setPreview(item);
    setPreviewPlayUrl(null);
    setPreviewError(null);
    resolvePreview.mutate(item);
  };

  const closePreview = () => {
    setPreview(null);
    setPreviewPlayUrl(null);
    setPreviewError(null);
  };

  const handleAdd = async (item: SearchResultItem) => {
    if (busyAdd || addedUrls.has(item.url)) return;
    setAddingUrl(item.url);
    setAddError(null);
    try {
      await onAddUrl(item.url);
      setAddedUrls((prev) => {
        const next = new Set(prev);
        next.add(item.url);
        return next;
      });
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : "加入失败，请重试");
    } finally {
      setAddingUrl(null);
    }
  };

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      >
        <div
          className="flex max-h-[min(92vh,880px)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-soft-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <header className="flex items-start justify-between gap-3 border-b border-border/50 px-5 py-4">
            <div className="min-w-0 pr-2">
              <h2 className="text-base font-semibold tracking-tight">网页搜索</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                搜索并加入当前笔记本
              </p>
            </div>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 shrink-0 rounded-full"
              onClick={() => onOpenChange(false)}
              aria-label="关闭"
            >
              <X className="h-4 w-4" />
            </Button>
          </header>

          <div className="space-y-3 border-b border-border/40 px-5 py-3.5">
            <div className="flex gap-2">
              <div className="relative min-w-0 flex-1">
                <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-10 rounded-full border-border/70 bg-background pl-9 text-sm shadow-none"
                  placeholder="输入关键词，例如：跑步训练、AI 学习…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") runSearch();
                  }}
                  aria-label="搜索关键词"
                  autoFocus
                />
              </div>
              <Button
                type="button"
                className="h-10 shrink-0 rounded-full px-5 text-sm shadow-glow"
                disabled={!query.trim() || search.isPending}
                onClick={runSearch}
              >
                {search.isPending ? (
                  <>
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    搜索中
                  </>
                ) : (
                  "搜索"
                )}
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="平台">
              {PLATFORM_CHIPS.map((chip) => {
                const active = platform === chip.id;
                return (
                  <button
                    key={chip.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setPlatform(chip.id)}
                    className={cn(
                      "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                      active
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    {chip.label}
                  </button>
                );
              })}
              {result && !search.isPending ? (
                <span className="ml-auto text-[11px] text-muted-foreground">
                  {searchedQuery ? `「${searchedQuery}」· ` : ""}
                  {items.length} 条
                </span>
              ) : null}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
            {search.isError ? (
              <div className="mx-2 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {search.error instanceof ApiError
                  ? search.error.message
                  : "搜索失败，请稍后重试"}
              </div>
            ) : null}

            {addError ? (
              <div className="mx-2 mb-2 rounded-xl border border-amber-300/60 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
                {addError}
              </div>
            ) : null}

            {search.isPending ? (
              <div className="space-y-2 px-1 py-1">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex gap-3 rounded-xl border border-border/40 p-2.5"
                  >
                    <div className="search-skel h-[4.5rem] w-[7.5rem] shrink-0 rounded-lg" />
                    <div className="flex flex-1 flex-col justify-center gap-2">
                      <div className="search-skel h-3.5 w-[88%]" />
                      <div className="search-skel h-3 w-[70%]" />
                      <div className="search-skel h-3 w-[40%]" />
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            {!search.isPending && result && items.length === 0 ? (
              <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
                <SearchIcon className="mb-3 h-8 w-8 text-muted-foreground/35" />
                <p className="text-sm font-medium">没有找到视频</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  换个关键词，或切换上方平台再试
                </p>
              </div>
            ) : null}

            {!search.isPending && !result && !search.isError ? (
              <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
                <SearchIcon className="mb-3 h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">输入关键词开始搜索</p>
                <p className="mt-1.5 text-xs text-muted-foreground/80">
                  支持 B站 · YouTube · 点加入即可入库
                </p>
              </div>
            ) : null}

            {!search.isPending && items.length > 0 ? (
              <div className="space-y-2">
                {errors.length > 0 ? (
                  <p className="px-2 pb-1 text-[11px] leading-relaxed text-amber-700">
                    部分平台未返回：
                    {errors
                      .map(
                        (e) =>
                          `${PLATFORM_ERROR_LABEL[e.platform] || e.platform}（${e.message}）`,
                      )
                      .join(" · ")}
                  </p>
                ) : null}
                {items.map((item) => {
                  const badge = PLATFORM_BADGE[item.platform];
                  const duration = formatDuration(item.duration);
                  const views = formatCount(item.view_count);
                  const comments = formatCount(item.comment_count);
                  const isThisAdding = addingUrl === item.url;
                  const already = addedUrls.has(item.url);
                  return (
                    <article
                      key={`${item.platform}-${item.id}`}
                      className="flex gap-3 rounded-xl border border-border/50 bg-background/60 p-2.5 transition-colors hover:border-primary/25 hover:bg-primary/[0.03]"
                    >
                      <button
                        type="button"
                        className="relative h-[4.5rem] w-[7.5rem] shrink-0 overflow-hidden rounded-lg bg-muted"
                        onClick={() => openPreview(item)}
                        aria-label={`预览：${item.title}`}
                      >
                        {item.thumbnail ? (
                          <img
                            src={item.thumbnail}
                            alt=""
                            className="h-full w-full object-cover"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center text-[10px] text-muted-foreground">
                            无封面
                          </div>
                        )}
                        <span
                          className={cn(
                            "absolute left-1 top-1 rounded px-1 py-px text-[9px] font-semibold",
                            badge.className,
                          )}
                        >
                          {badge.label}
                        </span>
                        {duration ? (
                          <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 py-px text-[9px] font-medium text-white">
                            {duration}
                          </span>
                        ) : null}
                      </button>

                      <div className="flex min-w-0 flex-1 flex-col">
                        <button
                          type="button"
                          className="line-clamp-2 text-left text-[13px] font-semibold leading-snug tracking-tight hover:text-primary"
                          title={item.title}
                          onClick={() => openPreview(item)}
                        >
                          {item.title}
                        </button>
                        <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-muted-foreground">
                          {item.uploader ? (
                            <span className="max-w-[9rem] truncate">{item.uploader}</span>
                          ) : null}
                          {item.uploader && views ? <span aria-hidden>·</span> : null}
                          {views ? (
                            <span className="inline-flex items-center gap-0.5" title="播放量">
                              <Play className="h-3 w-3 opacity-70" aria-hidden />
                              {views}
                            </span>
                          ) : null}
                          {(item.uploader || views) && comments ? (
                            <span aria-hidden>·</span>
                          ) : null}
                          {comments ? (
                            <span className="inline-flex items-center gap-0.5" title="评论数">
                              <MessageSquare className="h-3 w-3 opacity-70" aria-hidden />
                              {comments}
                            </span>
                          ) : null}
                          {!item.uploader && !views && !comments ? "—" : null}
                        </div>
                        <div className="mt-auto flex items-center justify-end gap-2 pt-2">
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="h-3 w-3" />
                            原站
                          </a>
                          <button
                            type="button"
                            disabled={busyAdd || already}
                            onClick={() => void handleAdd(item)}
                            className={cn(
                              "inline-flex h-6 items-center gap-0.5 rounded-full px-2.5 text-[11px] font-medium transition-colors",
                              already
                                ? "bg-muted text-muted-foreground"
                                : "bg-primary/10 text-primary hover:bg-primary/15 disabled:opacity-60",
                            )}
                          >
                            {isThisAdding ? (
                              <>
                                <Loader2 className="h-3 w-3 animate-spin" />
                                加入中
                              </>
                            ) : already ? (
                              "已加入"
                            ) : (
                              <>
                                <Plus className="h-3 w-3" />
                                加入
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : null}
          </div>

          <footer className="border-t border-border/50 px-5 py-2.5 text-[11px] text-muted-foreground">
            加入后会出现在左侧来源列表
          </footer>
        </div>
      </div>

      {preview ? (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={closePreview}
        >
          <div
            className="search-preview-modal w-full max-w-3xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-start justify-between gap-3 border-b border-border/50 px-4 py-3">
              <div className="min-w-0">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset",
                      PLATFORM_BADGE[preview.platform].soft,
                    )}
                  >
                    {PLATFORM_BADGE[preview.platform].label}
                  </span>
                  {preview.uploader ? (
                    <span className="truncate text-xs text-muted-foreground">
                      {preview.uploader}
                    </span>
                  ) : null}
                </div>
                <h2 className="line-clamp-2 text-sm font-semibold leading-snug">
                  {preview.title}
                </h2>
              </div>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0 rounded-full"
                onClick={closePreview}
                aria-label="关闭预览"
              >
                <X className="h-4 w-4" />
              </Button>
            </header>

            <div className="aspect-video bg-player">
              {previewPlayUrl ? (
                <video
                  key={previewPlayUrl}
                  src={previewPlayUrl}
                  className="h-full w-full"
                  controls
                  autoPlay
                  playsInline
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-sm text-player-foreground/80">
                  {previewBusy ? (
                    <>
                      <Loader2 className="h-6 w-6 animate-spin text-white/80" />
                      <p>正在解析可播放地址…</p>
                    </>
                  ) : (
                    <>
                      <p className="max-w-sm text-white/85">
                        {previewError || "该平台暂不支持页内预览"}
                      </p>
                      <Button
                        type="button"
                        variant="secondary"
                        className="rounded-full"
                        onClick={() => resolvePreview.mutate(preview)}
                      >
                        重试
                      </Button>
                    </>
                  )}
                </div>
              )}
            </div>

            <footer className="border-t border-border/50 bg-card px-4 py-3">
              <p className="text-xs text-muted-foreground">
                在结果列表中可加入或打开原站
              </p>
            </footer>
          </div>
        </div>
      ) : null}
    </>,
    document.body,
  );
}
