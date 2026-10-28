import { Link } from "react-router-dom";
import { Brand } from "@/components/brand";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export type AppNavKey = "mine" | "discover" | "collections" | "admin";

const NAV_ITEMS: { key: AppNavKey; label: string; to: string; adminOnly?: boolean }[] = [
  { key: "mine", label: "我的笔记本", to: "/" },
  { key: "discover", label: "发现", to: "/discover" },
  { key: "collections", label: "集合", to: "/?tab=collections" },
  { key: "admin", label: "后台配置", to: "/admin", adminOnly: true },
];

interface AppHeaderProps {
  active?: AppNavKey | null;
  rightSlot?: React.ReactNode;
  /** 导航与右侧之间的额外内容（如首页搜索框） */
  afterNav?: React.ReactNode;
  className?: string;
  sticky?: boolean;
}

export function AppHeader({
  active = null,
  rightSlot,
  afterNav,
  className,
  sticky = true,
}: AppHeaderProps) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const visibleNav = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);

  return (
    <header
      className={cn(
        "app-header-shell",
        sticky && "sticky top-0",
        className,
      )}
    >
      <div className="flex h-16 w-full items-center gap-4 px-6 lg:px-8">
        <Link to="/" className="shrink-0 transition-opacity hover:opacity-90" aria-label="回到首页">
          <Brand />
        </Link>

        <nav className="nav-pill ml-2" aria-label="主导航">
          {visibleNav.map((item) => {
            const isActive = active === item.key;
            return (
              <Link
                key={item.key}
                to={item.to}
                className={cn(
                  "nav-pill-item",
                  isActive ? "nav-pill-item-active" : "nav-pill-item-idle",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {afterNav ? <div className="min-w-0 flex-1">{afterNav}</div> : <div className="flex-1" />}

        {rightSlot ? (
          <div className="ml-auto flex shrink-0 items-center gap-3">{rightSlot}</div>
        ) : null}
      </div>
    </header>
  );
}
