import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

interface LayoutProps {
  children: React.ReactNode;
  /** 头部右上角 slot */
  rightSlot?: React.ReactNode;
  className?: string;
}

export function Layout({ children, rightSlot, className }: LayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="flex h-14 w-full items-center justify-between px-6 lg:px-8">
          <div className="flex items-center gap-6">
            <Link to="/" className="font-semibold tracking-tight">
              video-notebook
            </Link>
            <nav className="flex items-center gap-4 text-sm text-muted-foreground">
              <Link to="/" className="hover:text-foreground">
                我的笔记本
              </Link>
              <Link to="/discover" className="hover:text-foreground">
                发现
              </Link>
              <Link to="/search" className="hover:text-foreground">
                聚合搜索
              </Link>
              <Link to="/collections" className="hover:text-foreground">
                集合
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-2">{rightSlot}</div>
        </div>
      </header>
      <main className={cn("w-full flex-1 px-6 py-6 lg:px-8", className)}>{children}</main>
    </div>
  );
}
