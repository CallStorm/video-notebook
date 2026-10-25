import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, Info } from "lucide-react";
import {
  AdminEmptyState,
  AdminLoading,
  AdminSectionCard,
  AdminStatusBadge,
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

interface RunEvent {
  seq: number;
  stage: string;
  status: string;
  summary: string | null;
  detail_json: string | null;
  error_text: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

interface RunItem {
  run_id: string;
  video_id: number | null;
  notebook_id: number | null;
  video_title?: string | null;
  stage: string;
  status: string;
  force: boolean;
  error_summary: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  event_count: number;
  events: RunEvent[];
}

const STATUS_LABEL: Record<string, string> = {
  running: "进行中",
  ok: "成功",
  failed: "失败",
  dropped: "已丢弃",
  started: "开始",
  skipped: "跳过",
};

const STAGE_RUN_LABEL: Record<string, string> = {
  full: "全流程",
  subtitle_only: "仅字幕",
  vector: "向量",
};

/** 效果图五步：入队 → 抓取 → 字幕 → 概览 → 向量 */
const CANONICAL_STAGES: { key: string; title: string; match: string[] }[] = [
  { key: "enqueue", title: "入队", match: ["enqueue"] },
  { key: "fetch", title: "抓取", match: ["fetch"] },
  { key: "asr", title: "字幕", match: ["asr", "subtitle"] },
  { key: "overview", title: "概览", match: ["overview"] },
  { key: "vector", title: "向量", match: ["vector"] },
];

function formatMs(ms: number | null | undefined) {
  if (ms == null) return null;
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 2 : 1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return `${m}:${String(rem).padStart(2, "0")}`;
}

function formatTime(iso: string | null | undefined) {
  if (!iso) return null;
  return iso.replace("T", " ").slice(0, 19);
}

function statusTone(status: string): "ok" | "danger" | "info" | "idle" | "warn" {
  if (status === "ok") return "ok";
  if (status === "failed" || status === "dropped") return "danger";
  if (status === "running" || status === "started") return "info";
  if (status === "skipped") return "warn";
  return "idle";
}

type NodeTone = "pending" | "ok" | "failed" | "running" | "skipped";

function pickStageEvent(events: RunEvent[], match: string[]): RunEvent | null {
  const matched = events.filter((e) => match.includes(e.stage));
  if (!matched.length) return null;
  const rank = (s: string) =>
    s === "failed" ? 4 : s === "ok" ? 3 : s === "skipped" ? 2 : s === "started" ? 1 : 0;
  return [...matched].sort((a, b) => rank(b.status) - rank(a.status) || b.seq - a.seq)[0];
}

function nodeTone(ev: RunEvent | null): NodeTone {
  if (!ev) return "pending";
  if (ev.status === "failed") return "failed";
  if (ev.status === "ok") return "ok";
  if (ev.status === "skipped") return "skipped";
  if (ev.status === "started" || ev.status === "running") return "running";
  return "pending";
}

function TimelineNode({ tone }: { tone: NodeTone }) {
  return (
    <span
      className={cn(
        "admin-pl-node",
        tone === "ok" && "admin-pl-node-ok",
        tone === "failed" && "admin-pl-node-failed",
        tone === "running" && "admin-pl-node-running",
        tone === "skipped" && "admin-pl-node-skipped",
        tone === "pending" && "admin-pl-node-pending",
      )}
      aria-hidden
    />
  );
}

function RunTimeline({ run }: { run: RunItem }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const stages = useMemo(
    () =>
      CANONICAL_STAGES.map((c) => {
        const ev = pickStageEvent(run.events ?? [], c.match);
        return { ...c, ev, tone: nodeTone(ev) };
      }),
    [run.events],
  );

  return (
    <ol className="admin-pl-timeline">
      {stages.map((s, idx) => {
        const key = s.key;
        const expanded = open[key] ?? Boolean(s.ev?.error_text);
        const logText =
          s.ev?.error_text ||
          s.ev?.detail_json ||
          (s.ev?.summary ? s.ev.summary : null);
        const hasBody = Boolean(logText || s.ev?.error_text);
        return (
          <li key={key} className="admin-pl-timeline-item">
            <div className="admin-pl-timeline-rail" aria-hidden>
              <TimelineNode tone={s.tone} />
              {idx < stages.length - 1 ? <span className="admin-pl-timeline-line" /> : null}
            </div>
            <div className="admin-pl-timeline-body">
              <button
                type="button"
                className="admin-pl-stage-head"
                onClick={() => hasBody && setOpen((p) => ({ ...p, [key]: !expanded }))}
                disabled={!hasBody}
              >
                <span className="font-medium text-foreground">{s.title}</span>
                <span className="text-xs text-muted-foreground">
                  {s.ev ? STATUS_LABEL[s.ev.status] ?? s.ev.status : run.status === "ok" || run.status === "failed" || run.status === "dropped" ? "未执行" : "未开始"}
                  {s.ev?.duration_ms != null ? ` · ${formatMs(s.ev.duration_ms)}` : ""}
                  {s.ev?.started_at ? ` · ${formatTime(s.ev.started_at)?.slice(11) ?? ""}` : ""}
                </span>
              </button>
              {s.ev?.summary && s.tone !== "pending" ? (
                <p className="admin-pl-stage-summary">{s.ev.summary}</p>
              ) : null}
              {expanded && logText && !s.ev?.error_text ? (
                <pre className="admin-pl-log">{logText}</pre>
              ) : null}
              {expanded && s.ev?.error_text ? (
                <div className="admin-pl-error">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
                  <div>
                    <div className="font-medium text-destructive">错误：</div>
                    <pre className="whitespace-pre-wrap break-words text-[11px] leading-relaxed text-destructive/90">
                      {s.ev.error_text}
                    </pre>
                  </div>
                </div>
              ) : null}
              {expanded && s.ev?.detail_json && s.ev?.error_text ? (
                <pre className="admin-pl-log mt-2">{s.ev.detail_json}</pre>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function NotebookNameCombobox({
  items,
  valueId,
  onChange,
}: {
  items: NotebookItem[];
  valueId: string;
  onChange: (id: string) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const selected = items.find((n) => String(n.id) === valueId);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!touched) {
      setQuery(selected ? selected.title || `笔记本 #${selected.id}` : "");
    }
  }, [selected, touched]);

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

  const applyPick = (nb: NotebookItem) => {
    onChange(String(nb.id));
    setQuery(nb.title || `笔记本 #${nb.id}`);
    setTouched(false);
    setOpen(false);
  };

  const commitTyped = () => {
    const q = query.trim().toLowerCase();
    if (!q) {
      onChange("");
      setTouched(false);
      return;
    }
    const exact = items.find(
      (n) => (n.title || `笔记本 #${n.id}`).toLowerCase() === q || String(n.id) === q,
    );
    if (exact) {
      applyPick(exact);
      return;
    }
    if (filtered.length === 1) {
      applyPick(filtered[0]);
      return;
    }
    if (selected) {
      const label = (selected.title || `笔记本 #${selected.id}`).toLowerCase();
      if (!label.includes(q) && String(selected.id) !== q) onChange("");
    }
    setTouched(false);
  };

  return (
    <div ref={wrapRef} className="admin-pl-name-combo relative min-w-[240px] max-w-md flex-1">
      <label className="mb-1 block text-xs text-muted-foreground">名称</label>
      <div className="relative">
        <input
          className="admin-input w-full pr-9"
          placeholder="选择或输入笔记本名称…"
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
              setQuery(selected ? selected.title || `笔记本 #${selected.id}` : "");
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
          className="admin-pl-name-menu absolute left-0 top-full z-50 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-border/70 bg-background py-1 shadow-soft"
          role="listbox"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-xs text-muted-foreground">无匹配笔记本</li>
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

function RunCard({ run }: { run: RunItem }) {
  const [expanded, setExpanded] = useState(false);
  const title =
    run.video_title?.trim() ||
    (run.video_id != null ? `来源 #${run.video_id}` : "笔记本向量");
  const toggle = () => setExpanded((v) => !v);

  return (
    <AdminSectionCard
      className="admin-pl-run-card"
      headerClassName="admin-pl-run-header"
      contentClassName={cn(!expanded && "hidden")}
      action={
        <button
          type="button"
          className="admin-pl-run-chevron"
          onClick={toggle}
          aria-expanded={expanded}
          aria-label={expanded ? "折叠时间线" : "展开时间线"}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
          />
        </button>
      }
      title={
        <button type="button" className="admin-pl-run-toggle" onClick={toggle} aria-expanded={expanded}>
          <span className="inline-flex min-w-0 flex-wrap items-center gap-2 text-left">
            <span className="font-medium">{title}</span>
            <AdminStatusBadge tone={statusTone(run.status)}>
              {STATUS_LABEL[run.status] ?? run.status}
            </AdminStatusBadge>
            <span className="text-xs font-normal text-muted-foreground">
              {STAGE_RUN_LABEL[run.stage] ?? run.stage}
              {run.force ? " · 强制" : ""}
            </span>
          </span>
        </button>
      }
      description={
        <button type="button" className="admin-pl-run-meta" onClick={toggle}>
          {formatTime(run.started_at) ?? "—"}
          {run.duration_ms != null ? ` · ${formatMs(run.duration_ms)}` : ""}
          {run.event_count ? ` · ${run.event_count} 事件` : ""}
          {run.video_id != null ? ` · video/${run.video_id}` : ""}
        </button>
      }
    >
      {run.error_summary ? (
        <div className="admin-pl-error mb-3">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
          <div className="text-sm text-destructive">{run.error_summary}</div>
        </div>
      ) : null}
      <RunTimeline run={run} />
    </AdminSectionCard>
  );
}

export function AdminPipelineLogsPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const [notebookId, setNotebookId] = useState<string>("");
  const [status, setStatus] = useState("");

  const settings = useQuery({
    queryKey: ["admin-obs-settings"],
    queryFn: () => api<ObsSettings>("/admin/observability/settings", { access: token }),
    enabled: !!token,
  });

  const notebooks = useQuery({
    queryKey: ["admin-pipeline-notebooks"],
    queryFn: () =>
      api<NotebookListResponse>("/notebooks?page=1&size=100", { access: token }),
    enabled: !!token,
  });

  useEffect(() => {
    if (notebookId) return;
    const items = notebooks.data?.items ?? [];
    if (items.length) setNotebookId(String(items[0].id));
  }, [notebooks.data, notebookId]);

  const enabled = !!settings.data?.pipeline_logs_enabled;
  const retention = settings.data?.retention_days ?? 7;

  const runs = useQuery({
    queryKey: ["admin-pipeline-runs", notebookId, status],
    queryFn: () => {
      const q = new URLSearchParams();
      if (notebookId) q.set("notebook_id", notebookId);
      if (status) q.set("status", status);
      q.set("include_events", "true");
      q.set("limit", "50");
      return api<{ items: RunItem[]; total: number }>(
        `/admin/observability/pipeline-runs?${q}`,
        { access: token },
      );
    },
    enabled: !!token && enabled && !!notebookId,
    refetchInterval: enabled ? 5000 : false,
  });

  return (
    <div className="space-y-5">
      {settings.isLoading ? <AdminLoading /> : null}
      {settings.error instanceof ApiError && (
        <p className="text-sm text-destructive">{settings.error.message}</p>
      )}

      {!settings.isLoading && !enabled ? (
        <AdminEmptyState
          title="流水线日志未启用"
          description="请到系统设置开启「启用流水线日志」后再查询运行时间线。"
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
          <AdminSectionCard
            title="筛选"
            className="admin-pl-filter-card"
            contentClassName="overflow-visible pb-1"
          >
            <div className="flex flex-wrap items-end gap-4">
              <NotebookNameCombobox
                items={notebooks.data?.items ?? []}
                valueId={notebookId}
                onChange={setNotebookId}
              />
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">状态</label>
                <select
                  className="admin-input w-36"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="">全部状态</option>
                  <option value="running">进行中</option>
                  <option value="ok">成功</option>
                  <option value="failed">失败</option>
                </select>
              </div>
              <span className="pb-2 text-xs text-muted-foreground">
                共 {runs.data?.total ?? 0} 条运行
              </span>
            </div>
          </AdminSectionCard>

          {!notebookId ? (
            <AdminEmptyState
              title="请选择笔记本"
              description="选择或输入笔记本名称后，会显示该笔记本下来源的处理时间线。"
            />
          ) : runs.isLoading ? (
            <AdminLoading />
          ) : !(runs.data?.items?.length) ? (
            <AdminEmptyState
              title="暂无流水线记录"
              description="对该笔记本的来源重新生成或抓取后，这里会出现时间线。"
            />
          ) : (
            <div className="space-y-4">
              {(runs.data?.items ?? []).map((r) => (
                <RunCard key={r.run_id} run={r} />
              ))}

              <p className="admin-pl-footer">
                <Info className="h-3.5 w-3.5 shrink-0" />
                仅保留最近 {retention} 天的流水线日志；更早记录会自动清理。点击卡片展开处理时间线。
              </p>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
