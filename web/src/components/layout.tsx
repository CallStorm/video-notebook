import { cn } from "@/lib/utils";
import { AppHeader, type AppNavKey } from "@/components/app-header";

interface LayoutProps {
  children: React.ReactNode;
  /** 头部右上角 slot */
  rightSlot?: React.ReactNode;
  className?: string;
  /** 高亮哪个主导航；后台可传 null */
  activeNav?: AppNavKey | null;
}

export function Layout({
  children,
  rightSlot,
  className,
  activeNav = null,
}: LayoutProps) {
  return (
    <div className="page-ambient flex min-h-screen flex-col">
      <AppHeader active={activeNav} rightSlot={rightSlot} sticky={false} />
      <main className={cn("w-full flex-1 px-6 py-6 lg:px-8", className)}>
        {children}
      </main>
    </div>
  );
}
