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
        <div className="container flex h-14 items-center justify-between">
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
              <Link to="/collections" className="hover:text-foreground">
                集合
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-2">{rightSlot}</div>
        </div>
      </header>
      <main className={cn("container flex-1 py-6", className)}>{children}</main>
    </div>
  );
}
