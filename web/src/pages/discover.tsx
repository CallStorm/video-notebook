import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Compass, Library, Search, Sparkles, Type, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GeneratedCover } from "@/components/generated-cover";
import { isRemoteCover } from "@/lib/cover-gen";
import { cn, formatDateZh } from "@/lib/utils";

type DiscoverScope = "all" | "mine" | "shared";
type DiscoverMode = "keyword" | "semantic";

interface DiscoverNotebook {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
  cover_url?: string | null;
  share_all: boolean;
  owner_id: number | null;
  owner_name: string | null;
  is_owner?: boolean | null;
  source_count: number;
  note_count: number;
  match_hint?: string | null;
  updated_at: string | null;
}

interface DiscoverListResponse {
  items: DiscoverNotebook[];
  total: number;
  page: number;
  size: number;
}

const SCOPE_CHIPS: { id: DiscoverScope; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "mine", label: "我的" },
  { id: "shared", label: "公开" },
];

const MODE_CHIPS: {
  id: DiscoverMode;
  label: string;
  icon: typeof Type;
}[] = [
  { id: "keyword", label: "关键词", icon: Type },
  { id: "semantic", label: "语义", icon: Sparkles },
];

/** 最低相似度预设（百分比）；默认 55 */
const MIN_SCORE_PRESETS = [40, 50, 55, 60, 70] as const;
const DEFAULT_MIN_SCORE_PCT = 55;
const MIN_SCORE_STORAGE_KEY = "vn.discover.minScorePct";

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

function loadMinScorePct(): number {
  try {
    const raw = localStorage.getItem(MIN_SCORE_STORAGE_KEY);
    if (raw == null) return DEFAULT_MIN_SCORE_PCT;
    const n = Number(raw);
    if (!Number.isFinite(n)) return DEFAULT_MIN_SCORE_PCT;
    if (MIN_SCORE_PRESETS.includes(n as (typeof MIN_SCORE_PRESETS)[number])) {
      return n;
    }
    // 允许自定义百分比，钳到 0~100
    return Math.max(0, Math.min(100, Math.round(n)));
  } catch {
    return DEFAULT_MIN_SCORE_PCT;
  }
}

function buildDiscoverPath(
  scope: DiscoverScope,
  mode: DiscoverMode,
  q: string,
  minScorePct: number,
): string {
  const params = new URLSearchParams();
  params.set("scope", scope);
  params.set("mode", mode);
  params.set("size", "50");
  const trimmed = q.trim();
  if (trimmed) params.set("q", trimmed);
  if (mode === "semantic" && trimmed) {
    const score = Math.max(0, Math.min(1, minScorePct / 100));
    params.set("min_score", score.toFixed(2));
  }
  return `/notebooks/discover?${params.toString()}`;
}

function placeholderFor(mode: DiscoverMode): string {
  return mode === "semantic"
    ? "用一句话描述你想找的内容，例如：怎么快速减脂"
    : "搜索标题、描述、概览";
}

export default function DiscoverPage() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";

  const [scope, setScope] = useState<DiscoverScope>("all");
  const [mode, setMode] = useState<DiscoverMode>("keyword");
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [minScorePct, setMinScorePct] = useState<number>(DEFAULT_MIN_SCORE_PCT);

  useEffect(() => {
    setMinScorePct(loadMinScorePct());
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(MIN_SCORE_STORAGE_KEY, String(minScorePct));
    } catch {
      /* ignore */
    }
  }, [minScorePct]);

  const list = useQuery({
    queryKey: ["notebooks-discover", scope, mode, query, minScorePct],
    queryFn: () =>
      api<DiscoverListResponse>(
        buildDiscoverPath(scope, mode, query, minScorePct),
        { access: token },
      ),
    enabled: !!token,
    retry: false,
  });

  const runSearch = () => setQuery(draft.trim());

  if (!token) {
    return (
      <div className="page-ambient mx-auto flex min-h-screen max-w-md items-center p-6">
        <div className="w-full soft-tile p-8 text-center">
          <p className="mb-4 text-sm text-muted-foreground">
            请先登录后浏览与搜索笔记本。
          </p>
          <Button asChild className="rounded-full">
            <Link to="/login">跳到登录页</Link>
          </Button>
        </div>
      </div>
    );
  }

  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const searching = Boolean(query);
  const errorMessage =
    list.isError && list.error instanceof ApiError
      ? list.error.message
      : list.isError
        ? mode === "semantic"
          ? "语义检索暂时不可用，请稍后重试或改用关键词。"
          : "加载失败，请稍后重试。"
        : null;

  return (
    <div className="page-ambient min-h-screen">
      <AppHeader
        active="discover"
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
        <div className="search-dock-inner max-w-none">
          <div className="mb-4">
            <h1 className="page-hero-title">发现</h1>
            <p className="page-hero-desc">
              搜索自己的笔记本，或浏览他人公开分享的本
            </p>
          </div>

          <div className="search-shell search-shell-lg max-w-3xl">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="h-12 border-0 bg-transparent pl-11 text-[15px] shadow-none placeholder:text-muted-foreground/80 focus-visible:ring-0"
                placeholder={placeholderFor(mode)}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runSearch();
                }}
                aria-label="搜索笔记本"
              />
            </div>
            <Button
              className="h-11 shrink-0 rounded-full px-7 text-[15px] shadow-glow"
              onClick={runSearch}
            >
              搜索
            </Button>
          </div>

          {/* 搜索条件：软面板分组 */}
          <div className="discover-filter-panel mt-3.5 max-w-3xl">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
              <div className="flex min-w-0 flex-1 flex-col gap-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="discover-filter-label">方式</span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {MODE_CHIPS.map((chip) => {
                      const active = mode === chip.id;
                      const Icon = chip.icon;
                      return (
                        <button
                          key={chip.id}
                          type="button"
                          onClick={() => setMode(chip.id)}
                          className={cn(
                            "platform-filter inline-flex items-center gap-1",
                            active
                              ? "platform-filter-active"
                              : "platform-filter-idle",
                          )}
                          aria-pressed={active}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {chip.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="discover-filter-label">范围</span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {SCOPE_CHIPS.map((chip) => {
                      const active = scope === chip.id;
                      return (
                        <button
                          key={chip.id}
                          type="button"
                          onClick={() => setScope(chip.id)}
                          className={cn(
                            "platform-filter",
                            active
                              ? "platform-filter-active"
                              : "platform-filter-idle",
                          )}
                          aria-pressed={active}
                        >
                          {chip.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {mode === "semantic" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="discover-filter-label">最低相似度</span>
                    <div
                      className="flex flex-wrap items-center gap-1.5"
                      role="group"
                      aria-label="最低相似度"
                    >
                      {MIN_SCORE_PRESETS.map((pct) => {
                        const active = minScorePct === pct;
                        return (
                          <button
                            key={pct}
                            type="button"
                            onClick={() => setMinScorePct(pct)}
                            className={cn(
                              "platform-filter tabular-nums",
                              active
                                ? "platform-filter-active"
                                : "platform-filter-idle",
                            )}
                            aria-pressed={active}
                          >
                            {pct}%
                          </button>
                        );
                      })}
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      低于此分的结果不展示
                    </span>
                  </div>
                ) : null}
              </div>

              {!list.isLoading && !list.isError ? (
                <p className="shrink-0 pt-0.5 text-xs text-muted-foreground">
                  {searching ? `「${query}」· ` : ""}
                  {total} 本
                  {mode === "semantic" && searching
                    ? ` · ≥${minScorePct}%`
                    : ""}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="w-full px-6 py-8 lg:px-8">
        {errorMessage ? (
          <div className="search-alert search-alert-error mb-6 max-w-3xl">
            {errorMessage}
          </div>
        ) : null}

        {list.isLoading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : list.isError ? (
          <div className="empty-hero">
            <div className="empty-hero-icon">
              <Compass className="h-7 w-7" />
            </div>
            <p className="mb-1 text-lg font-semibold tracking-tight">
              {mode === "semantic" ? "语义检索不可用" : "暂时无法加载"}
            </p>
            <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
              {mode === "semantic"
                ? "请确认后台已配置向量模型、Qdrant 已启动，或先改用「关键词」搜索。"
                : "请稍后重试。"}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2.5">
              {mode === "semantic" ? (
                <Button
                  className="rounded-full px-5"
                  onClick={() => setMode("keyword")}
                >
                  改用关键词
                </Button>
              ) : null}
              <Button
                variant="outline"
                className="rounded-full border-border/70 px-5"
                onClick={() => list.refetch()}
              >
                重试
              </Button>
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="empty-hero">
            <div className="empty-hero-icon">
              <Compass className="h-7 w-7" />
            </div>
            <p className="mb-1 text-lg font-semibold tracking-tight">
              {searching
                ? mode === "semantic"
                  ? "没有语义相近的笔记本"
                  : "没有找到相关笔记本"
                : emptyTitle(scope)}
            </p>
            <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
              {searching
                ? mode === "semantic"
                  ? `当前最低相似度 ${minScorePct}%。可调低阈值、换个说法，或切换到「关键词」。`
                  : "试试换个关键词，或切换上方的范围（全部 / 我的 / 公开）。"
                : emptyDesc(scope)}
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2.5">
              {searching ? (
                <>
                  {mode === "semantic" && minScorePct > 40 ? (
                    <Button
                      className="rounded-full px-5"
                      onClick={() => setMinScorePct(40)}
                    >
                      降到 40% 再搜
                    </Button>
                  ) : null}
                  <Button
                    variant="outline"
                    className="rounded-full border-border/70 px-5"
                    onClick={() => {
                      setDraft("");
                      setQuery("");
                    }}
                  >
                    清空搜索
                  </Button>
                  {mode === "semantic" ? (
                    <Button
                      className="rounded-full px-5"
                      onClick={() => setMode("keyword")}
                    >
                      改用关键词
                    </Button>
                  ) : null}
                </>
              ) : (
                <Button className="rounded-full px-5" onClick={() => navigate("/")}>
                  <Library className="h-4 w-4" />
                  <span className="ml-1">回到我的笔记本</span>
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-x-2.5 gap-y-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8">
            {items.map((nb) => (
              <DiscoverNotebookCard key={nb.id} notebook={nb} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function emptyTitle(scope: DiscoverScope): string {
  if (scope === "mine") return "你还没有笔记本";
  if (scope === "shared") return "暂时还没有公开笔记本";
  return "还没有可展示的笔记本";
}

function emptyDesc(scope: DiscoverScope): string {
  if (scope === "mine") return "去「我的笔记本」新建一本，或在上方搜索已有内容。";
  if (scope === "shared") {
    return "别人在「我的笔记本」卡片菜单里打开「公开分享」后，会出现在这里。";
  }
  return "创建笔记本，或等他人公开分享后，就可以在这里浏览与搜索。";
}

function DiscoverNotebookCard({ notebook: nb }: { notebook: DiscoverNotebook }) {
  const remote = isRemoteCover(nb.cover_url);
  const mine = Boolean(nb.is_owner);
  const ownerLabel = mine ? "我" : nb.owner_name?.trim() || "匿名用户";

  return (
    <article className="notebook-card group soft-tile soft-tile-hover flex flex-col overflow-hidden">
      <Link
        to={`/notebooks/${nb.id}`}
        className="relative block aspect-[3/4] w-full overflow-hidden bg-muted/30 text-left"
        aria-label={nb.title}
      >
        {remote ? (
          <img
            src={nb.cover_url!}
            alt=""
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <GeneratedCover
            title={nb.title}
            coverUrl={nb.cover_url}
            variant={nb.id}
            className="h-full w-full"
          />
        )}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-gradient-to-r from-black/25 via-white/20 to-transparent opacity-70"
        />
        <span
          className={cn(
            "absolute left-1.5 top-1.5 z-[1] inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-medium shadow-sm backdrop-blur-sm",
            mine
              ? "bg-white/90 text-violet-700"
              : "bg-white/90 text-emerald-700",
          )}
        >
          {mine ? <Library className="h-3 w-3" /> : <Users className="h-3 w-3" />}
          {mine ? "我的" : "公开"}
        </span>
      </Link>

      <div className="flex items-start gap-1.5 px-2 pb-2 pt-1.5">
        <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1 text-left">
          <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-foreground">
            {nb.title}
          </h3>
          {nb.match_hint ? (
            <p className="mt-0.5 text-[10px] font-medium text-primary/80">
              {nb.match_hint}
            </p>
          ) : null}
          <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-muted-foreground">
            <span className="inline-flex items-center rounded-full bg-muted/80 px-1.5 py-0.5 font-medium text-foreground/80">
              {formatSources(nb.source_count ?? 0)}
            </span>
            <span className="truncate">{ownerLabel}</span>
            {nb.updated_at ? (
              <span className="truncate">{formatDateZh(nb.updated_at)}</span>
            ) : null}
          </p>
        </Link>
      </div>
    </article>
  );
}
