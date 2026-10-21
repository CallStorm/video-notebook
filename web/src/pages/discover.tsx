import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Compass, Library, Search, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";
import { GeneratedCover } from "@/components/generated-cover";
import { isRemoteCover } from "@/lib/cover-gen";
import { formatDateZh } from "@/lib/utils";

interface SharedNotebook {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
  cover_url?: string | null;
  share_all: boolean;
  owner_id: number | null;
  owner_name: string | null;
  source_count: number;
  note_count: number;
  updated_at: string | null;
}

interface SharedListResponse {
  items: SharedNotebook[];
  total: number;
  page: number;
  size: number;
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

export default function DiscoverPage() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";

  const list = useQuery({
    queryKey: ["notebooks-shared"],
    queryFn: () =>
      api<SharedListResponse>("/notebooks/shared?size=50", { access: token }),
    enabled: !!token,
  });

  if (!token) {
    return (
      <div className="page-ambient mx-auto flex min-h-screen max-w-md items-center p-6">
        <div className="w-full soft-tile p-8 text-center">
          <p className="mb-4 text-sm text-muted-foreground">请先登录后浏览公开笔记本。</p>
          <Button asChild className="rounded-full">
            <Link to="/login">跳到登录页</Link>
          </Button>
        </div>
      </div>
    );
  }

  const items = list.data?.items ?? [];

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
      <div className="w-full px-6 py-8 lg:px-8">
        <header className="page-hero">
          <div>
            <h1 className="page-hero-title">发现</h1>
            <p className="page-hero-desc">浏览他人公开分享的笔记本</p>
          </div>
        </header>

        {list.isLoading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : items.length === 0 ? (
          <div className="empty-hero">
            <div className="empty-hero-icon">
              <Compass className="h-7 w-7" />
            </div>
            <p className="mb-1 text-lg font-semibold tracking-tight">暂时还没有公开笔记本</p>
            <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
              别人在「我的笔记本」卡片菜单里打开「公开分享」后，会出现在这里。你自己的本仍在「我的笔记本」。
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2.5">
              <Button className="rounded-full px-5" onClick={() => navigate("/")}>
                <Library className="h-4 w-4" />
                <span className="ml-1">回到我的笔记本</span>
              </Button>
              <Button
                variant="outline"
                className="rounded-full border-border/70 px-5"
                onClick={() => navigate("/search")}
              >
                <Search className="h-4 w-4" />
                <span className="ml-1">去聚合搜索</span>
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-x-3 gap-y-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7">
            {items.map((nb) => (
              <SharedNotebookCard key={nb.id} notebook={nb} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SharedNotebookCard({ notebook: nb }: { notebook: SharedNotebook }) {
  const remote = isRemoteCover(nb.cover_url);
  const ownerLabel = nb.owner_name?.trim() || "匿名用户";

  return (
    <article className="notebook-card group soft-tile soft-tile-hover flex flex-col overflow-hidden">
      <Link
        to={`/notebooks/${nb.id}`}
        className="notebook-cover relative block w-full overflow-hidden text-left"
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
        <span className="absolute left-2 top-2 z-[1] inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-emerald-700 shadow-sm backdrop-blur-sm">
          <Users className="h-3 w-3" />
          公开
        </span>
      </Link>

      <div className="flex items-start gap-1.5 px-2.5 pb-2.5 pt-2">
        <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1 text-left">
          <h3 className="line-clamp-2 text-[13px] font-semibold leading-snug tracking-tight text-foreground">
            {nb.title}
          </h3>
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
