import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Clapperboard,
  ExternalLink,
  Eye,
  Loader2,
  NotebookPen,
  Play,
  Search as SearchIcon,
  X,
} from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { UserMenu } from "@/components/user-menu";
import {
  AddSearchToNotebookDialog,
  type SearchVideoRef,
} from "@/components/add-search-to-notebook-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { RequireAuth } from "@/components/require-auth";
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

const PLATFORM_CHIPS: {
  id: "all" | Platform;
  label: string;
  hint: string;
  tone: string;
}[] = [
  { id: "all", label: "全部", hint: "三平台一起搜", tone: "platform-chip-all" },
  { id: "bilibili", label: "B站", hint: "Bilibili", tone: "platform-chip-bili" },
  { id: "youtube", label: "YouTube", hint: "YouTube", tone: "platform-chip-yt" },
  // douyin temporarily disabled from aggregate UI
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

function formatViews(n: number | null): string | null {
  if (n == null) return null;
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}亿`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}万`;
  return String(n);
}

function SearchSkeleton() {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="search-skel-card">
          <div className="search-skel aspect-video rounded-none" />
          <div className="space-y-2.5 p-4">
            <div className="search-skel h-4 w-[92%]" />
            <div className="search-skel h-4 w-[68%]" />
            <div className="search-skel h-3 w-[42%]" />
          </div>
        </div>
      ))}
    </div>
  );
}

function SearchPageInner() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState<"all" | Platform>("all");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [preview, setPreview] = useState<SearchResultItem | null>(null);
  const [previewPlayUrl, setPreviewPlayUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [addVideo, setAddVideo] = useState<SearchVideoRef | null>(null);
  const [searchedQuery, setSearchedQuery] = useState("");

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
        err instanceof ApiError ? err.message : "预览解析失败，请重试或打开原站",
      );
    },
  });

  const items = result?.items ?? [];
  const errors = result?.errors ?? [];
  const previewBusy = resolvePreview.isPending;
  const activeChip = PLATFORM_CHIPS.find((c) => c.id === platform);

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

  return (
    <div className="page-ambient min-h-screen">
      <AppHeader
        active="search"
        rightSlot={
          <UserMenu
            onLogout={() => {
              logout();
              navigate("/login", { replace: true });
            }}
          />
        }
      />

      <div className="search-dock sticky top-16 z-10">
        <div className="search-dock-inner">
          <div className="search-shell-wrap">
          <div className="search-shell search-shell-lg">
            <div className="relative min-w-0 flex-1">
              <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="h-11 border-0 bg-transparent pl-11 text-[14px] shadow-none placeholder:text-muted-foreground/80 focus-visible:ring-0"
                placeholder="输入关键词，例如：AI 学习方法、经济下行应对…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runSearch();
                }}
                aria-label="搜索关键词"
              />
            </div>
            <Button
              className="h-10 shrink-0 rounded-full px-6 text-sm shadow-glow"
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
          </div>

          {/* Google 式：主 Tab=平台；右侧=类型提示 + 结果数 */}
          <div className="search-tabs-bar">
            <div className="search-tabs" role="tablist" aria-label="平台">
              {PLATFORM_CHIPS.map((chip) => {
                const active = platform === chip.id;
                return (
                  <button
                    key={chip.id}
                    type="button"
                    role="tab"
                    title={chip.hint}
                    aria-selected={active}
                    onClick={() => setPlatform(chip.id)}
                    className={cn("search-tab", active && "search-tab-active")}
                  >
                    {chip.label}
                  </button>
                );
              })}
            </div>
            <div className="search-tabs-meta">
              <span>仅视频 · 暂不支持图文/合集</span>
              {result && !search.isPending ? (
                <span>
                  {searchedQuery ? `「${searchedQuery}」· ` : ""}
                  {items.length} 条
                </span>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <main className="w-full px-6 py-8 lg:px-8">
        {search.isError && (
          <div className="search-alert search-alert-error mb-6">
            {search.error instanceof ApiError
              ? search.error.message
              : "搜索失败，请稍后重试"}
          </div>
        )}

        {search.isPending && <SearchSkeleton />}

        {!search.isPending && result && (
          <div className="space-y-5">
            {errors.length > 0 ? (
              <p className="max-w-3xl text-xs leading-relaxed text-amber-700">
                部分平台未返回：
                {errors
                  .map(
                    (e) =>
                      `${PLATFORM_ERROR_LABEL[e.platform] || e.platform}（${e.message}）`,
                  )
                  .join(" · ")}
              </p>
            ) : null}

            {items.length === 0 ? (
              <div className="empty-hero py-14">
                <div className="empty-hero-icon">
                  <SearchIcon className="h-6 w-6" />
                </div>
                <p className="mb-1 text-base font-semibold tracking-tight">
                  没有找到视频
                </p>
                <p className="text-sm text-muted-foreground">
                  换个关键词，或切换上方平台再试
                </p>
              </div>
            ) : (
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                {items.map((item) => {
                  const badge = PLATFORM_BADGE[item.platform];
                  const duration = formatDuration(item.duration);
                  const views = formatViews(item.view_count);
                  const comments = formatViews(item.comment_count);
                  return (
                    <article
                      key={`${item.platform}-${item.id}`}
                      className="search-result-card group"
                    >
                      <button
                        type="button"
                        className="search-thumb"
                        onClick={() => openPreview(item)}
                        aria-label={`预览：${item.title}`}
                      >
                        {item.thumbnail ? (
                          <img
                            src={item.thumbnail}
                            alt=""
                            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center bg-muted/50 text-xs text-muted-foreground">
                            无封面
                          </div>
                        )}
                        <span
                          className={cn(
                            "absolute left-2.5 top-2.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold shadow-sm",
                            badge.className,
                          )}
                        >
                          {badge.label}
                        </span>
                        {duration && (
                          <span className="absolute bottom-2.5 right-2.5 rounded-md bg-black/75 px-1.5 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm">
                            {duration}
                          </span>
                        )}
                        <span className="search-thumb-play" aria-hidden>
                          <Play className="h-5 w-5 fill-current" />
                        </span>
                      </button>

                      <div className="flex flex-1 flex-col gap-2.5 p-3.5 pt-3">
                        <h3
                          className="line-clamp-2 min-h-[2.5rem] text-[14px] font-semibold leading-snug tracking-tight text-foreground"
                          title={item.title}
                        >
                          {item.title}
                        </h3>
                        <p className="truncate text-xs text-muted-foreground">
                          {[
                            item.uploader,
                            views ? `${views} 播放` : null,
                            comments ? `${comments} 评论` : null,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </p>
                        <div className="mt-auto flex items-center gap-1.5 pt-0.5">
                          <Button
                            type="button"
                            size="sm"
                            className="h-8 flex-1 gap-1 rounded-full text-xs shadow-none"
                            onClick={() =>
                              setAddVideo({ title: item.title, url: item.url })
                            }
                          >
                            <NotebookPen className="h-3.5 w-3.5" />
                            加入笔记本
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="outline"
                            className="h-8 w-8 shrink-0 rounded-full border-border/70"
                            title="页内预览"
                            onClick={() => openPreview(item)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 shrink-0 rounded-full"
                            title="打开原站"
                            onClick={() =>
                              window.open(item.url, "_blank", "noopener,noreferrer")
                            }
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {!result && !search.isPending && !search.isError && (
          <div className="relative mx-auto flex min-h-[18rem] max-w-lg flex-col items-center justify-center px-6 py-16 text-center">
            <Clapperboard
              className="pointer-events-none mb-5 h-16 w-16 text-muted-foreground/20"
              strokeWidth={1.25}
              aria-hidden
            />
            <p className="text-sm text-muted-foreground">
              输入关键词开始搜索
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground/80">
              支持 B站 · YouTube · 点封面可预览
            </p>
          </div>
        )}
      </main>

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
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
                  {preview.uploader && (
                    <span className="truncate text-xs text-muted-foreground">
                      {preview.uploader}
                    </span>
                  )}
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
                在结果卡片中可加入笔记本或打开原站
              </p>
            </footer>
          </div>
        </div>
      )}

      <AddSearchToNotebookDialog
        open={!!addVideo}
        video={addVideo}
        onOpenChange={(open) => {
          if (!open) setAddVideo(null);
        }}
        onAdded={(notebookId) => navigate(`/notebooks/${notebookId}`)}
      />
    </div>
  );
}

export default function SearchPage() {
  return (
    <RequireAuth>
      <SearchPageInner />
    </RequireAuth>
  );
}
