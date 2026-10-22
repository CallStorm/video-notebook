import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** 每个后台 Tab 顶部：标题 + 中文说明 + 可选右侧操作 */
export function AdminPageHeader({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("admin-page-header", className)}>
      <div className="min-w-0 flex-1">
        <h2 className="admin-page-title">{title}</h2>
        {description ? <p className="admin-page-desc">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/** 分区卡片：统一圆角、内边距与标题层级 */
export function AdminSectionCard({
  title,
  description,
  children,
  className,
  headerClassName,
  contentClassName,
  action,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  headerClassName?: string;
  contentClassName?: string;
  action?: ReactNode;
}) {
  const hasHeader = Boolean(title || description || action);
  return (
    <Card className={cn("admin-section-card", className)}>
      {hasHeader ? (
        <CardHeader className={cn("admin-section-header", headerClassName)}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              {title ? <CardTitle className="admin-section-title">{title}</CardTitle> : null}
              {description ? (
                <CardDescription className="admin-section-desc">{description}</CardDescription>
              ) : null}
            </div>
            {action ? <div className="shrink-0">{action}</div> : null}
          </div>
        </CardHeader>
      ) : null}
      <CardContent className={cn(hasHeader ? "pt-0" : "pt-6", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}

export function AdminEmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="admin-empty">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function AdminStatusBadge({
  tone = "idle",
  children,
}: {
  tone?: "ok" | "warn" | "idle" | "info" | "danger";
  children: ReactNode;
}) {
  return <span className={cn("admin-badge", `admin-badge-${tone}`)}>{children}</span>;
}

export function AdminFieldLabel({
  htmlFor,
  children,
  hint,
}: {
  htmlFor?: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="admin-field-label">
        {children}
      </label>
      {hint ? <p className="text-[11px] leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function AdminLoading({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
      <span className="inline-block h-3.5 w-3.5 animate-pulse rounded-full bg-primary/40" />
      {label}
    </div>
  );
}

/** 表格外壳：横向滚动 + 统一表头/行样式 */
export function AdminTableShell({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("admin-table-shell", className)}>
      <table className="admin-table">{children}</table>
    </div>
  );
}
