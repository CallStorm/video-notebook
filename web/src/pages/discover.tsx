import { Link, useNavigate } from "react-router-dom";
import { Compass, Plus, Search } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { AppHeader } from "@/components/app-header";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";

export default function DiscoverPage() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";

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
            <p className="page-hero-desc">
              浏览他人分享的公开笔记本
            </p>
          </div>
        </header>

        <div className="empty-hero">
          <div className="empty-hero-icon">
            <Compass className="h-7 w-7" />
          </div>
          <p className="mb-1 text-lg font-semibold tracking-tight">公开笔记本即将上线</p>
          <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
            功能尚未开放。可先回自己的笔记本，或去聚合搜索找视频。
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            <Button className="rounded-full px-5" onClick={() => navigate("/")}>
              <Plus className="h-4 w-4" />
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
      </div>
    </div>
  );
}
