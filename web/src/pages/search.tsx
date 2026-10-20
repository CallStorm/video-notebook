import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Clapperboard,
  ExternalLink,
  Eye,
  NotebookPen,
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
  { id: "douyin", label: "抖音" },
];

const PLATFORM_BADGE: Record<Platform, { label: string; className: string }> = {
  youtube: { label: "YT", className: "bg-red-600 text-white" },
  bilibili: { label: "B站", className: "bg-pink-500 text-white" },
  douyin: { label: "抖音", className: "bg-zinc-900 text-white" },
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
    onSuccess: (data) => setResult(data),
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

  const previewBusy = resolvePreview.isPending;

  return (
    <div className="min-h-screen bg-background">
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

      <main className="w-full px-6 py-8 lg:px-8">
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="h-11 pl-9"
                placeholder="输入关键词搜索视频…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && query.trim() && !search.isPending) {
                    search.mutate();
                  }
                }}
              />
            </div>
            <Button
              className="h-11 rounded-full px-6 shadow-none"
              disabled={!query.trim() || search.isPending}
              onClick={() => search.mutate()}
            >
              {search.isPending ? "搜索中…" : "搜索"}
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {PLATFORM_CHIPS.map((chip) => (
              <button
                key={chip.id}
                type="button"
                onClick={() => setPlatform(chip.id)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                  platform === chip.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                {chip.label}
              </button>
            ))}
            <span className="self-center text-xs text-muted-foreground">仅视频</span>
          </div>
        </div>

        {search.isError && (
          <p className="mt-6 text-center text-sm text-destructive">
            {search.error instanceof ApiError
              ? search.error.message
              : "搜索失败"}
          </p>
        )}

        {result && (
          <div className="mt-8 space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm text-muted-foreground">
                共找到约 {items.length} 个结果
              </p>
              {errors.length > 0 && (
                <p className="text-xs text-amber-600">
                  {errors.map((e) => `${e.platform}: ${e.message}`).join(" · ")}
                </p>
              )}
            </div>

            {items.length === 0 ? (
              <div className="soft-tile py-14 text-center">
                <p className="mb-1 text-sm font-medium">没有找到视频</p>
                <p className="text-sm text-muted-foreground">换个关键词，或切换上方平台再试一次</p>
              </div>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                {items.map((item) => {
                  const badge = PLATFORM_BADGE[item.platform];
                  const duration = formatDuration(item.duration);
                  const views = formatViews(item.view_count);
                  return (
                    <article
                      key={`${item.platform}-${item.id}`}
                      className="flex flex-col overflow-hidden soft-tile soft-tile-hover"
                    >
                      <div className="relative aspect-video overflow-hidden bg-background/60">
                        {item.thumbnail ? (
                          <img
                            src={item.thumbnail}
                            alt=""
                            className="h-full w-full object-cover"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                            无封面
                          </div>
                        )}
                        <span
                          className={`absolute left-2.5 top-2.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                        {duration && (
                          <span className="absolute bottom-2.5 right-2.5 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] text-white">
                            {duration}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-1 flex-col gap-2 p-4">
                        <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight">
                          {item.title}
                        </h3>
                        <p className="text-xs text-muted-foreground">
                          {[item.uploader, views ? `${views} 次观看` : null]
                            .filter(Boolean)
                            .join(" · ") || "—"}
                        </p>
                        <div className="mt-auto flex gap-1 pt-1">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="flex-1 gap-1 rounded-full text-xs"
                            onClick={() => window.open(item.url, "_blank", "noopener,noreferrer")}
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            跳转
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="flex-1 gap-1 rounded-full text-xs text-emerald-700"
                            onClick={() => openPreview(item)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                            预览
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            className="flex-1 gap-1 rounded-full text-xs shadow-none"
                            onClick={() =>
                              setAddVideo({ title: item.title, url: item.url })
                            }
                          >
                            <NotebookPen className="h-3.5 w-3.5" />
                            添加
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

        {!result && !search.isPending && (
          <div className="mx-auto mt-14 max-w-lg soft-tile px-8 py-14 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Clapperboard className="h-6 w-6" />
            </div>
            <p className="mb-1 text-base font-semibold tracking-tight">找视频，加进笔记本</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              输入关键词，搜索 B站、YouTube、抖音。预览后一键添加到笔记本，进入「分析 → 学习 → 输出」。
            </p>
          </div>
        )}
      </main>

      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={closePreview}
        >
          <div
            className="w-full max-w-3xl overflow-hidden rounded-xl border bg-background shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="truncate pr-4 text-sm font-semibold">{preview.title}</h2>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8 shrink-0"
                onClick={closePreview}
              >
                <X className="h-4 w-4" />
              </Button>
            </header>
            <div className="aspect-video bg-black">
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
                <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
                  {previewBusy ? (
                    <p>正在解析可播放地址…</p>
                  ) : (
                    <>
                      <p>{previewError || "该平台暂不支持页内预览"}</p>
                      <div className="flex flex-wrap justify-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => resolvePreview.mutate(preview)}
                        >
                          重试
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() =>
                            window.open(preview.url, "_blank", "noopener,noreferrer")
                          }
                        >
                          打开原站观看
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
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
