import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, X } from "lucide-react";
import {
  AdminEmptyState,
  AdminLoading,
  AdminSectionCard,
  AdminStatusBadge,
  AdminTableShell,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface ObsSettings {
  pipeline_logs_enabled: boolean;
  llm_traces_enabled: boolean;
  retention_days: number;
  success_sample_rate: number;
  llm_record_full: boolean;
  llm_truncate_chars: number;
  max_pipeline_run_rows: number;
  max_llm_trace_rows: number;
  langfuse_enabled: boolean;
}

interface NotebookItem {
  id: number;
  title: string;
}

interface NotebookListResponse {
  items: NotebookItem[];
  total: number;
}

interface TraceItem {
  trace_id: string;
  kind: string;
  status: string;
  notebook_id: number | null;
  notebook_title?: string | null;
  video_id: number | null;
  thread_id: number | null;
  message_id: number | null;
  provider: string | null;
  model_name: string | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  error_text: string | null;
  started_at: string | null;
  finished_at: string | null;
}

interface SpanItem {
  seq: number;
  name: string;
  role: string | null;
  content_text: string | null;
  content_chars: number;
  truncated: boolean;
  created_at: string | null;
}

interface TraceDetail extends TraceItem {
  spans: SpanItem[];
}

/** 与后端 start_llm_trace(kind=...) 对齐；概览 = overview */
const KIND_LABEL: Record<string, string> = {
  chat: "对话",
  overview: "概览",
  studio: "产物",
  tags: "标签",
};

const KIND_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "全部" },
  { value: "overview", label: "概览" },
  { value: "chat", label: "对话" },
  { value: "studio", label: "产物" },
  { value: "tags", label: "标签" },
];

const STATUS_LABEL: Record<string, string> = {
  ok: "成功",
  success: "成功",
  failed: "失败",
  error: "失败",
  running: "运行中",
};

function formatMs(ms: number | null | undefined) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

function formatTokens(t: TraceItem) {
  if (t.prompt_tokens == null && t.completion_tokens == null) return "—";
  const total = (t.prompt_tokens ?? 0) + (t.completion_tokens ?? 0);
  const a = t.prompt_tokens ?? "—";
  const b = t.completion_tokens ?? "—";
  return `${total}（${a}+${b}）`;
}

function statusTone(status: string): "ok" | "danger" | "info" | "idle" | "warn" {
  if (status === "ok" || status === "success") return "ok";
  if (status === "failed" || status === "error") return "danger";
  if (status === "running") return "info";
  return "idle";
}

function KindBadge({ kind }: { kind: string }) {
  const label = KIND_LABEL[kind] ?? kind;
  const tone =
    kind === "overview"
      ? "bg-sky-50 text-sky-800 ring-sky-200/80"
      : kind === "chat"
        ? "bg-emerald-50 text-emerald-800 ring-emerald-200/80"
        : kind === "studio"
          ? "bg-violet-50 text-violet-800 ring-violet-200/80"
          : "bg-muted text-muted-foreground ring-border/60";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-none ring-1 ring-inset",
        tone,
      )}
    >
      {label}
    </span>
  );
}

function NotebookNameCombobox({
  items,
  valueId,
  onChange,
  compact,
}: {
  items: NotebookItem[];
  valueId: string;
  onChange: (id: string) => void;
  compact?: boolean;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const selected = items.find((n) => String(n.id) === valueId);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!touched) {
      if (!valueId) setQuery("");
      else setQuery(selected ? selected.title || `笔记本 #${selected.id}` : `笔记本 #${valueId}`);
    }
  }, [selected, touched, valueId]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setTouched(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((n) => {
      const title = (n.title || `笔记本 #${n.id}`).toLowerCase();
      return title.includes(q) || String(n.id).includes(q);
    });
  }, [items, query]);

  const applyPick = (nb: NotebookItem | null) => {
    if (!nb) {
      onChange("");
      setQuery("");
    } else {
      onChange(String(nb.id));
      setQuery(nb.title || `笔记本 #${nb.id}`);
    }
    setTouched(false);
    setOpen(false);
  };

  const commitTyped = () => {
    const q = query.trim();
    const ql = q.toLowerCase();
    if (!q) {
      applyPick(null);
      return;
    }
    if (/^\d+$/.test(q)) {
      onChange(q);
      const hit = items.find((n) => String(n.id) === q);
      setQuery(hit ? hit.title || `笔记本 #${hit.id}` : `笔记本 #${q}`);
      setTouched(false);
      setOpen(false);
      return;
    }
    const exact = items.find(
      (n) => (n.title || `笔记本 #${n.id}`).toLowerCase() === ql || String(n.id) === q,
    );
    if (exact) {
      applyPick(exact);
      return;
    }
    if (filtered.length === 1) {
      applyPick(filtered[0]);
      return;
    }
    setTouched(false);
  };

  return (
    <div
      ref={wrapRef}
      className={cn(
      "relative",
      compact
        ? "w-[13rem] min-w-0 shrink-0"
        : "min-w-[200px] max-w-sm flex-1",
    )}
    >
      {!compact ? (
        <label className="mb-1 block text-xs text-muted-foreground">笔记本</label>
      ) : null}
      <div className="relative">
        <input
          className={cn("admin-input w-full pr-9", compact && "h-9 rounded-lg text-xs")}
          placeholder="全部笔记本 / 名称 / ID…"
          value={query}
          onChange={(e) => {
            setTouched(true);
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commitTyped();
              setOpen(false);
            } else if (e.key === "Escape") {
              setOpen(false);
              setTouched(false);
              if (!valueId) setQuery("");
              else
                setQuery(
                  selected ? selected.title || `笔记本 #${selected.id}` : `笔记本 #${valueId}`,
                );
            } else if (e.key === "ArrowDown") {
              setOpen(true);
            }
          }}
          onBlur={() => {
            window.setTimeout(() => {
              if (!wrapRef.current?.contains(document.activeElement)) {
                commitTyped();
                setOpen(false);
              }
            }, 120);
          }}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          aria-label="笔记本"
        />
        <button
          type="button"
          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted"
          aria-label="打开笔记本列表"
          tabIndex={-1}
          onMouseDown={(e) => {
            e.preventDefault();
            setOpen((v) => !v);
          }}
        >
          <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
        </button>
      </div>
      {open ? (
        <ul
          className="absolute left-0 top-full z-50 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-border/70 bg-background py-1 shadow-soft"
          role="listbox"
        >
          <li role="option" aria-selected={!valueId}>
            <button
              type="button"
              className={cn(
                "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted/70",
                !valueId && "bg-primary/10 text-foreground",
              )}
              onMouseDown={(e) => {
                e.preventDefault();
                applyPick(null);
              }}
            >
              <span>全部笔记本</span>
            </button>
          </li>
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-xs text-muted-foreground">
              无匹配；可直接输入笔记本数字 ID（含已删除）
            </li>
          ) : (
            filtered.map((nb) => {
              const label = nb.title || `笔记本 #${nb.id}`;
              const active = String(nb.id) === valueId;
              return (
                <li key={nb.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    className={cn(
                      "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted/70",
                      active && "bg-primary/10 text-foreground",
                    )}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      applyPick(nb);
                    }}
                  >
                    <span className="truncate">{label}</span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">#{nb.id}</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}

function KindSegmented({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div
      className="inline-flex shrink-0 rounded-lg border border-border/60 bg-muted/30 p-0.5"
      role="tablist"
      aria-label="类型"
    >
      {KIND_OPTIONS.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value || "all"}
            type="button"
            role="tab"
            aria-selected={active}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-xs font-medium transition",
              active
                ? "bg-background text-foreground shadow-soft"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function AdminLlmTracesPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [notebookId, setNotebookId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const settings = useQuery({
    queryKey: ["admin-obs-settings"],
    queryFn: () => api<ObsSettings>("/admin/observability/settings", { access: token }),
    enabled: !!token,
  });

  const notebooks = useQuery({
    queryKey: ["admin-llm-trace-notebooks"],
    queryFn: () =>
      api<NotebookListResponse>("/notebooks?page=1&size=100", { access: token }),
    enabled: !!token,
  });

  const enabled = !!settings.data?.llm_traces_enabled;

  const traces = useQuery({
    queryKey: ["admin-llm-traces", kind, status, notebookId],
    queryFn: () => {
      const q = new URLSearchParams();
      if (kind) q.set("kind", kind);
      if (status) q.set("status", status);
      if (notebookId) q.set("notebook_id", notebookId);
      q.set("limit", "50");
      return api<{ items: TraceItem[]; total: number }>(
        `/admin/observability/llm-traces?${q}`,
        { access: token },
      );
    },
    enabled: !!token && enabled,
    refetchInterval: enabled ? 5000 : false,
  });

  const detail = useQuery({
    queryKey: ["admin-llm-trace", selected],
    queryFn: () =>
      api<TraceDetail>(`/admin/observability/llm-traces/${selected}`, {
        access: token,
      }),
    enabled: !!token && !!selected,
  });

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [selected]);

  const promptSpans =
    detail.data?.spans.filter((s) => s.name !== "generation" && s.role !== "assistant") ?? [];
  const completionSpans =
    detail.data?.spans.filter(
      (s) => s.name === "generation" || s.role === "assistant",
    ) ?? [];

  // 始终展示 Token 列，便于核对消耗；无用量时显示 —
  const hasTokenCol = true;

  return (
    <div className="space-y-4">
      {settings.isLoading ? <AdminLoading /> : null}
      {settings.error instanceof ApiError && (
        <p className="text-sm text-destructive">{settings.error.message}</p>
      )}

      {!settings.isLoading && !enabled ? (
        <AdminEmptyState
          title="LLM 追踪未启用"
          description="请到系统设置开启「启用 LLM 追踪」后再查看对话、概览与产物调用。"
          action={
            <Link
              to="/admin?section=settings"
              className="inline-flex rounded-full bg-primary px-3.5 py-1.5 text-xs font-medium text-primary-foreground shadow-soft hover:opacity-95"
            >
              前往系统设置 →
            </Link>
          }
        />
      ) : null}

      {enabled ? (
        <>
          {/* 方案 A：单行紧凑工具栏；状态与标签同组，避免 admin-input 的 w-full 把下拉挤换行 */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-border/60 bg-card/80 px-3 py-2.5 shadow-soft">
            <div className="flex min-w-0 items-center gap-2">
              <span className="shrink-0 text-[11px] font-medium text-muted-foreground">笔记本</span>
              <NotebookNameCombobox
                compact
                items={notebooks.data?.items ?? []}
                valueId={notebookId}
                onChange={(id) => {
                  setNotebookId(id);
                  setSelected(null);
                }}
              />
            </div>
            <span className="hidden h-4 w-px shrink-0 bg-border/70 sm:block" aria-hidden />
            <div className="flex shrink-0 items-center gap-2">
              <span className="shrink-0 text-[11px] font-medium text-muted-foreground">类型</span>
              <KindSegmented
                value={kind}
                onChange={(v) => {
                  setKind(v);
                  setSelected(null);
                }}
              />
            </div>
            <span className="hidden h-4 w-px shrink-0 bg-border/70 sm:block" aria-hidden />
            <div className="flex shrink-0 items-center gap-2">
              <span className="shrink-0 text-[11px] font-medium text-muted-foreground">状态</span>
              <select
                className="admin-input !h-9 !w-[7.5rem] shrink-0 rounded-lg text-xs"
                value={status}
                aria-label="状态"
                onChange={(e) => {
                  setStatus(e.target.value);
                  setSelected(null);
                }}
              >
                <option value="">全部状态</option>
                <option value="ok">成功</option>
                <option value="failed">失败</option>
                <option value="running">运行中</option>
              </select>
            </div>
            <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
              共 {traces.data?.total ?? 0} 条
            </span>
          </div>

          <AdminSectionCard
            title="追踪列表"
            description={`最近 ${traces.data?.items?.length ?? 0} 条 · 共 ${traces.data?.total ?? 0} · 点击行查看详情`}
            contentClassName="pt-0"
          >
            {traces.isLoading ? <AdminLoading /> : null}
            {traces.error instanceof ApiError ? (
              <p className="text-sm text-destructive">{traces.error.message}</p>
            ) : null}
            {!traces.isLoading && !(traces.data?.items?.length) ? (
              <AdminEmptyState
                title="暂无追踪"
                description={
                  kind || notebookId || status
                    ? "当前筛选无结果，试试放宽条件。"
                    : "去对话页问一句、生成概览或跑产物任务试试。"
                }
              />
            ) : null}
            {(traces.data?.items?.length ?? 0) > 0 ? (
              <AdminTableShell className="admin-llm-trace-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>笔记本</th>
                    <th>模型</th>
                    {hasTokenCol ? <th>Token 合计</th> : null}
                    <th>耗时</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {(traces.data?.items ?? []).map((t) => {
                    const active = selected === t.trace_id;
                    const nbLabel =
                      t.notebook_id != null
                        ? t.notebook_title
                          ? t.notebook_title
                          : `#${t.notebook_id}`
                        : "—";
                    return (
                      <tr
                        key={t.trace_id}
                        className={cn(
                          "cursor-pointer",
                          active && "bg-primary/5",
                        )}
                        onClick={() => setSelected(t.trace_id)}
                      >
                        <td className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                          {formatTime(t.started_at)}
                        </td>
                        <td>
                          <KindBadge kind={t.kind} />
                        </td>
                        <td className="max-w-[10rem] truncate text-xs" title={nbLabel}>
                          {nbLabel}
                          {t.notebook_id != null && t.notebook_title ? (
                            <span className="ml-1 text-muted-foreground">#{t.notebook_id}</span>
                          ) : null}
                        </td>
                        <td className="max-w-[9rem] truncate text-xs text-muted-foreground" title={t.model_name ?? undefined}>
                          {t.model_name ?? "—"}
                        </td>
                        {hasTokenCol ? (
                          <td className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                            {formatTokens(t)}
                          </td>
                        ) : null}
                        <td className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                          {formatMs(t.latency_ms)}
                        </td>
                        <td>
                          <AdminStatusBadge tone={statusTone(t.status)}>
                            {STATUS_LABEL[t.status] ?? t.status}
                          </AdminStatusBadge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </AdminTableShell>
            ) : null}
          </AdminSectionCard>

          {/* 右侧滑动详情抽屉 */}
          {selected ? (
            <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Trace 详情">
              <button
                type="button"
                className="absolute inset-0 bg-black/35 backdrop-blur-[1px] transition-opacity"
                aria-label="关闭"
                onClick={() => setSelected(null)}
              />
              <aside
                className="relative flex h-full w-full max-w-lg animate-in slide-in-from-right duration-200 flex-col border-l border-border/60 bg-card shadow-soft-md"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-foreground">Trace 详情</div>
                    <div className="truncate font-mono text-[11px] text-muted-foreground">{selected}</div>
                  </div>
                  <button
                    type="button"
                    className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    aria-label="关闭详情"
                    onClick={() => setSelected(null)}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-4">
                  {detail.isLoading ? <AdminLoading /> : null}
                  {detail.error instanceof ApiError ? (
                    <p className="text-sm text-destructive">{detail.error.message}</p>
                  ) : null}
                  {!detail.isLoading && detail.data ? (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
                        <KindBadge kind={detail.data.kind} />
                        <AdminStatusBadge tone={statusTone(detail.data.status)}>
                          {STATUS_LABEL[detail.data.status] ?? detail.data.status}
                        </AdminStatusBadge>
                        <span className="font-medium text-foreground">
                          {detail.data.notebook_id != null
                            ? detail.data.notebook_title || `笔记本 #${detail.data.notebook_id}`
                            : "无笔记本"}
                        </span>
                        <span className="ml-auto tabular-nums">{formatTime(detail.data.started_at)}</span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
                          <div className="text-[11px] text-muted-foreground">模型</div>
                          <div className="mt-0.5 truncate font-medium text-foreground" title={detail.data.model_name ?? undefined}>
                            {detail.data.model_name ?? "—"}
                          </div>
                          {detail.data.provider ? (
                            <div className="text-[11px] text-muted-foreground">{detail.data.provider}</div>
                          ) : null}
                        </div>
                        <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
                          <div className="text-[11px] text-muted-foreground">耗时</div>
                          <div className="mt-0.5 font-medium tabular-nums text-foreground">
                            {formatMs(detail.data.latency_ms)}
                          </div>
                        </div>
                        <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
                          <div className="text-[11px] text-muted-foreground">输入 Token</div>
                          <div className="mt-0.5 font-medium tabular-nums text-foreground">
                            {detail.data.prompt_tokens ?? "—"}
                          </div>
                        </div>
                        <div className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2">
                          <div className="text-[11px] text-muted-foreground">输出 Token</div>
                          <div className="mt-0.5 font-medium tabular-nums text-foreground">
                            {detail.data.completion_tokens ?? "—"}
                          </div>
                        </div>
                      </div>

                      {detail.data.error_text ? (
                        <pre className="rounded-lg border border-destructive/20 bg-destructive/5 p-2 text-[11px] text-destructive">
                          {detail.data.error_text}
                        </pre>
                      ) : null}

                      <div>
                        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Span 树
                        </h3>
                        <ul className="space-y-1.5">
                          {detail.data.spans.map((s) => (
                            <li
                              key={`${s.seq}-${s.name}`}
                              className="flex items-center justify-between gap-2 rounded-lg border border-border/50 bg-muted/20 px-2.5 py-1.5 text-xs"
                            >
                              <span className="font-medium">
                                {s.seq}. {s.name}
                                {s.role ? ` · ${s.role}` : ""}
                              </span>
                              <span className="text-muted-foreground">
                                {s.content_chars} 字
                                {s.truncated ? " · 已截断" : ""}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {promptSpans.length ? (
                        <div>
                          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Prompt 预览
                          </h3>
                          <div className="space-y-2">
                            {promptSpans.map((s) => (
                              <div
                                key={`p-${s.seq}-${s.name}`}
                                className="rounded-xl border border-border/60 px-3 py-2"
                              >
                                <div className="text-xs font-medium text-foreground">
                                  {s.name}
                                  {s.role ? ` · ${s.role}` : ""}
                                </div>
                                {s.content_text ? (
                                  <pre className="mt-1.5 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground">
                                    {s.content_text}
                                  </pre>
                                ) : (
                                  <p className="mt-1 text-[11px] text-muted-foreground">（无正文）</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {completionSpans.length ? (
                        <div>
                          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Completion 预览
                          </h3>
                          <div className="space-y-2">
                            {completionSpans.map((s) => (
                              <div
                                key={`c-${s.seq}-${s.name}`}
                                className="rounded-xl border border-border/60 px-3 py-2"
                              >
                                <div className="text-xs font-medium text-foreground">
                                  {s.name}
                                  {s.role ? ` · ${s.role}` : ""}
                                </div>
                                {s.content_text ? (
                                  <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground">
                                    {s.content_text}
                                  </pre>
                                ) : (
                                  <p className="mt-1 text-[11px] text-muted-foreground">（无正文）</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      <div className="rounded-xl border border-border/60 bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
                        <div className="font-medium text-foreground">汇总</div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                          <span>输入 {detail.data.prompt_tokens ?? "—"}</span>
                          <span>输出 {detail.data.completion_tokens ?? "—"}</span>
                          <span>
                            合计{" "}
                            {detail.data.prompt_tokens != null &&
                            detail.data.completion_tokens != null
                              ? detail.data.prompt_tokens + detail.data.completion_tokens
                              : "—"}
                          </span>
                          <span>延迟 {formatMs(detail.data.latency_ms)}</span>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {!detail.isLoading && !detail.data && !(detail.error instanceof ApiError) ? (
                    <p className="text-sm text-destructive">加载失败</p>
                  ) : null}
                </div>
              </aside>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
