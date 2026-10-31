import { BookOpen, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

export type RightPanelMode = "knowledge" | "studio";

export function RightPanelTabs({
  mode,
  onChange,
  studioBusyCount = 0,
}: {
  mode: RightPanelMode;
  onChange: (mode: RightPanelMode) => void;
  studioBusyCount?: number;
}) {
  const tabs: {
    id: RightPanelMode;
    label: string;
    icon: typeof BookOpen;
    badge: number | undefined;
  }[] = [
    { id: "knowledge", label: "知识", icon: BookOpen, badge: undefined },
    {
      id: "studio",
      label: "产物",
      icon: Sparkles,
      badge: studioBusyCount > 0 ? studioBusyCount : undefined,
    },
  ];

  return (
    <div
      className="inline-flex min-w-0 max-w-full items-center rounded-full border border-border/60 bg-muted/50 p-1 shadow-soft"
      role="tablist"
      aria-label="右侧面板"
    >
      {tabs.map((tab) => {
        const active = mode === tab.id;
        const Icon = tab.icon;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={cn(
              "relative inline-flex h-9 items-center gap-2 rounded-full px-3.5 text-sm font-medium transition",
              active
                ? "bg-primary text-primary-foreground shadow-glow"
                : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
            )}
            onClick={() => onChange(tab.id)}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            <span>{tab.label}</span>
            {tab.badge != null ? (
              <span
                className={cn(
                  "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-semibold leading-none",
                  active
                    ? "bg-primary-foreground/20 text-primary-foreground"
                    : "bg-primary/15 text-primary",
                )}
                aria-label={`${tab.badge} 个进行中任务`}
              >
                {tab.badge > 9 ? "9+" : tab.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}