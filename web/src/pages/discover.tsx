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
      <div className="mx-auto flex min-h-screen max-w-md items-center p-6">
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
    <div className="min-h-screen bg-background">
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
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">发现</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            浏览他人分享的公开笔记本，找灵感、复用学习路径
          </p>
        </header>

        <div className="soft-tile overflow-hidden px-6 py-16 text-center sm:px-10">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Compass className="h-7 w-7" />
          </div>
          <p className="mb-1 text-lg font-semibold tracking-tight">公开笔记本即将上线</p>
          <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
            之后你可以在这里看到社区精选与同事分享的笔记本。现在先从自己的书架开始，或用聚合搜索找视频素材。
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            <Button
              className="rounded-full px-5 shadow-none"
              onClick={() => navigate("/")}
            >
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
