import { Link } from "react-router-dom";
import { Brand } from "@/components/brand";
import { cn } from "@/lib/utils";

export type AppNavKey = "mine" | "discover" | "search" | "collections";

const NAV_ITEMS: { key: AppNavKey; label: string; to: string }[] = [
  { key: "mine", label: "我的笔记本", to: "/" },
  { key: "discover", label: "发现", to: "/discover" },
  { key: "search", label: "聚合搜索", to: "/search" },
  { key: "collections", label: "集合", to: "/?tab=collections" },
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
  return (
    <header
      className={cn(
        "z-20 border-b border-border/40 bg-background/85 backdrop-blur-md",
        sticky && "sticky top-0",
        className,
      )}
    >
      <div className="flex h-16 w-full items-center gap-4 px-6 lg:px-8">
        <Link to="/" className="shrink-0" aria-label="回到首页">
          <Brand />
        </Link>

        <nav
          className="ml-2 flex items-center gap-1 rounded-full border border-border/70 bg-card p-1 shadow-soft"
          aria-label="主导航"
        >
          {NAV_ITEMS.map((item) => {
            const isActive = active === item.key;
            return (
              <Link
                key={item.key}
                to={item.to}
                className={cn(
                  "rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
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
