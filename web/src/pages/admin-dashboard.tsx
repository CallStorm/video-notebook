import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Film,
  Info,
  NotebookPen,
  RefreshCw,
  Share2,
} from "lucide-react";
import {
  AdminEmptyState,
  AdminLoading,
} from "@/components/admin-shell";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CallCount {
  count: number | null;
  unavailable: boolean;
  reason: string | null;
}

interface DailyCount {
  date: string;
  llm: number | null;
  embed: number | null;
  asr: number | null;
  tts: number | null;
  tokens: number | null;
}

interface ReadinessRate {
  ready: number;
  total: number;
  rate: number | null;
}

interface AdminStats {
  observability: {
    pipeline_logs_enabled: boolean;
    llm_traces_enabled: boolean;
  };
  content: {
    notebooks: number;
    videos: number;
    notes: number;
    share_all_notebooks: number;
  };
  model_calls: {
    llm: CallCount;
    embed: CallCount;
    asr: CallCount;
    tts: CallCount;
    trend_7d: DailyCount[];
  };
  tokens: {
    total: number | null;
    unavailable: boolean;
    reason: string | null;
    trend_7d: DailyCount[];
  };
  queues: {
    media_depth: number | null;
    studio_depth: number | null;
    index_backlog: number;
    studio_queued: number;
    redis_ok: boolean;
    redis_error: string | null;
  };
  readiness: {
    subtitle: ReadinessRate;
    overview: ReadinessRate;
    vector: ReadinessRate;
    complete_notebooks: ReadinessRate;
  };
  failures: {
    top: { stage: string; count: number; label: string | null }[];
    window_hours: number;
    note: string | null;
  };
}

type SeriesKey = "llm" | "embed" | "asr" | "tts";

const SERIES: {
  key: SeriesKey;
  label: string;
  color: string;
}[] = [
  { key: "llm", label: "LLM", color: "#2A9B7A" },
  { key: "embed", label: "Embed", color: "#5B8DEF" },
  { key: "asr", label: "语音转文字", color: "#E8A838" },
  { key: "tts", label: "文字转语音", color: "#C45BA8" },
];

function fmtNum(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("zh-CN");
}

function fmtPct(rate: number | null | undefined) {
  if (rate == null) return "—";
  return `${(rate * 100).toFixed(rate >= 0.1 ? 0 : 1)}%`;
}

function fmtTokens(n: number | null | undefined) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function shortDate(iso: string) {
  const parts = iso.split("-");
  if (parts.length < 3) return iso;
  return `${Number(parts[1])}/${Number(parts[2])}`;
}

function Panel({
  title,
  hint,
  action,
  children,
  className,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("admin-dash-panel", className)}>
      <header className="admin-dash-panel-head">
        <div className="min-w-0">
          <h3 className="admin-dash-panel-title">{title}</h3>
          {hint ? <p className="admin-dash-panel-hint">{hint}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      <div className="admin-dash-panel-body">{children}</div>
    </section>
  );
}

function MultiLineChart({
  days,
  focus,
}: {
  days: DailyCount[];
  focus: SeriesKey | "all";
}) {
  const w = 420;
  const h = 140;
  const padX = 10;
  const padY = 14;

  const seriesVals = SERIES.map((s) => ({
    ...s,
    values: days.map((d) => {
      const v = d[s.key];
      return v == null ? null : Number(v);
    }),
  }));

  const allNums = seriesVals.flatMap((s) =>
    s.values.filter((v): v is number => v != null),
  );
  if (allNums.length === 0) {
    return <div className="admin-dash-chart-empty">暂无调用趋势（Embed / TTS 等可能尚未埋点）</div>;
  }

  const max = Math.max(...allNums, 1);
  const min = 0;
  const span = Math.max(max - min, 1);
  const n = Math.max(days.length - 1, 1);

  function point(i: number, v: number) {
    const x = padX + (i / n) * (w - padX * 2);
    const y = h - padY - ((v - min) / span) * (h - padY * 2);
    return { x, y };
  }

  return (
    <div className="admin-dash-chart">
      <svg viewBox={`0 0 ${w} ${h}`} className="admin-dash-chart-svg" role="img" aria-label="近 7 日模型调用趋势">
        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1={padX}
            x2={w - padX}
            y1={padY + g * (h - padY * 2)}
            y2={padY + g * (h - padY * 2)}
            stroke="hsl(var(--border))"
            strokeOpacity="0.55"
            strokeDasharray="3 4"
          />
        ))}
        {seriesVals.map((s) => {
          const pts = s.values
            .map((v, i) => (v == null ? null : point(i, v)))
            .filter(Boolean) as { x: number; y: number }[];
          if (pts.length === 0) return null;
          const active = focus === "all" || focus === s.key;
          const opacity = active ? 1 : 0.18;
          const width = active ? 2.75 : 1.5;
          const linePts = pts.map((p) => `${p.x},${p.y}`).join(" ");
          return (
            <g key={s.key} opacity={opacity} style={{ transition: "opacity 0.2s ease" }}>
              <polyline
                fill="none"
                stroke={s.color}
                strokeWidth={width}
                strokeLinejoin="round"
                strokeLinecap="round"
                points={linePts}
              />
              {pts.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={active ? 3.4 : 2.2}
                  fill={s.color}
                  stroke="hsl(var(--card))"
                  strokeWidth="1.4"
                />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="admin-dash-chart-labels">
        {days.map((d, i) => (
          <span key={d.date}>
            {i === 0 || i === days.length - 1 || i === Math.floor(days.length / 2)
              ? shortDate(d.date)
              : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function TokenBars({
  days,
}: {
  days: { date: string; tokens: number | null }[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const present = days.map((d) => d.tokens).filter((v): v is number => v != null);
  if (present.length === 0) {
    return <div className="admin-dash-chart-empty">暂无 Token 趋势</div>;
  }
  const max = Math.max(...present, 1);
  const tip = hover != null ? days[hover] : null;

  return (
    <div className="admin-dash-chart admin-dash-bars-wrap">
      <div className="admin-dash-bars" onMouseLeave={() => setHover(null)}>
        {days.map((d, i) => {
          const v = d.tokens;
          const h = v == null ? 6 : Math.max(10, (v / max) * 100);
          return (
            <div
              key={d.date}
              className={cn("admin-dash-bar-col", hover === i && "is-hover")}
              onMouseEnter={() => setHover(i)}
            >
              <div
                className={cn("admin-dash-bar", v == null && "admin-dash-bar-empty")}
                style={{ height: `${h}%` }}
              />
            </div>
          );
        })}
      </div>
      {tip ? (
        <div className="admin-dash-bar-tooltip" role="tooltip">
          <div className="admin-dash-bar-tooltip-date">{tip.date}</div>
          <div className="admin-dash-bar-tooltip-val tabular-nums">
            {tip.tokens == null ? "暂无数据" : `${fmtNum(tip.tokens)} tokens`}
          </div>
        </div>
      ) : null}
      <div className="admin-dash-chart-labels">
        {days.map((d, i) => (
          <span key={d.date}>
            {i === 0 || i === days.length - 1 || i === Math.floor(days.length / 2)
              ? shortDate(d.date)
              : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function RateRing({ label, rate }: { label: string; rate: ReadinessRate }) {
  const pct = rate.rate == null ? 0 : Math.round(rate.rate * 100);
  const r = 30;
  const c = 2 * Math.PI * r;
  const dash = rate.rate == null ? 0 : (pct / 100) * c;
  return (
    <div className="admin-dash-ring">
      <svg width="76" height="76" viewBox="0 0 76 76" aria-hidden>
        <circle cx="38" cy="38" r={r} fill="none" stroke="hsl(var(--border))" strokeWidth="6.5" />
        <circle
          cx="38"
          cy="38"
          r={r}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth="6.5"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          transform="rotate(-90 38 38)"
        />
        <text x="38" y="42" textAnchor="middle" className="admin-dash-ring-text">
          {fmtPct(rate.rate)}
        </text>
      </svg>
      <div className="admin-dash-ring-label">{label}</div>
      <div className="admin-dash-ring-sub tabular-nums">
        {rate.ready}/{rate.total}
      </div>
    </div>
  );
}

export function AdminDashboard() {
  const [focus, setFocus] = useState<SeriesKey | "all">("all");
  const q = useQuery({
    queryKey: ["admin-stats"],
    queryFn: () => api<AdminStats>("/admin/stats"),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: 30_000,
  });

  const data = q.data;
  const obsNotes = useMemo(() => {
    if (!data) return [] as string[];
    const notes: string[] = [];
    if (!data.observability.pipeline_logs_enabled) {
      notes.push("流水线日志未开启：ASR 与失败 TOP 可能不完整");
    }
    if (!data.observability.llm_traces_enabled) {
      notes.push("LLM 追踪未开启：调用与 Token 暂不可信");
    }
    return notes;
  }, [data]);

  if (q.isLoading) {
    return <AdminLoading label="加载运营总览…" />;
  }

  if (q.isError) {
    const err = q.error;
    const msg =
      err instanceof ApiError ? err.message : err instanceof Error ? err.message : "加载失败";
    return (
      <AdminEmptyState
        title="无法加载运营总览"
        description={msg}
        action={
          <Button type="button" variant="outline" className="rounded-full" onClick={() => q.refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  if (!data) return null;

  const maxFail = Math.max(1, ...data.failures.top.map((t) => t.count));
  const callByKey = {
    llm: data.model_calls.llm,
    embed: data.model_calls.embed,
    asr: data.model_calls.asr,
    tts: data.model_calls.tts,
  } as const;

  return (
    <div className="admin-dash">
      <div className="admin-dash-toolbar">
        <p className="admin-dash-lede">内容资产、调用与就绪一览 · 缺埋点项灰显</p>
        <Button
          type="button"
          size="sm"
          className="rounded-full shadow-soft"
          onClick={() => q.refetch()}
          disabled={q.isFetching}
        >
          <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", q.isFetching && "animate-spin")} />
          刷新
        </Button>
      </div>

      {obsNotes.length > 0 ? (
        <div className="admin-dash-banner">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-80" />
          <div className="space-y-0.5">
            {obsNotes.map((n) => (
              <div key={n}>{n}</div>
            ))}
            <div className="opacity-75">可在「系统设置」开启观测。</div>
          </div>
        </div>
      ) : null}

      {/* 内容资产大卡 + 共享小卡 */}
      <div className="admin-dash-assets-row">
        <section className="admin-dash-assets-card">
          <div className="admin-dash-assets-head">
            <h3 className="admin-dash-panel-title">内容资产</h3>
            <p className="admin-dash-panel-hint">笔记本 · 视频 · 笔记</p>
          </div>
          <div className="admin-dash-assets-cols">
            <div className="admin-dash-asset-col">
              <span className="admin-dash-kpi-icon" aria-hidden>
                <BookOpen className="h-4 w-4" />
              </span>
              <div className="admin-dash-kpi-label">笔记本</div>
              <div className="admin-dash-kpi-value tabular-nums">{fmtNum(data.content.notebooks)}</div>
            </div>
            <div className="admin-dash-asset-col">
              <span className="admin-dash-kpi-icon" aria-hidden>
                <Film className="h-4 w-4" />
              </span>
              <div className="admin-dash-kpi-label">视频</div>
              <div className="admin-dash-kpi-value tabular-nums">{fmtNum(data.content.videos)}</div>
            </div>
            <div className="admin-dash-asset-col">
              <span className="admin-dash-kpi-icon" aria-hidden>
                <NotebookPen className="h-4 w-4" />
              </span>
              <div className="admin-dash-kpi-label">笔记</div>
              <div className="admin-dash-kpi-value tabular-nums">{fmtNum(data.content.notes)}</div>
            </div>
          </div>
        </section>

        <section className="admin-dash-share-card">
          <div className="admin-dash-kpi-top">
            <span className="admin-dash-kpi-label">全站共享</span>
            <span className="admin-dash-kpi-icon" aria-hidden>
              <Share2 className="h-4 w-4" />
            </span>
          </div>
          <div className="admin-dash-kpi-value tabular-nums">
            {fmtNum(data.content.share_all_notebooks)}
          </div>
          <p className="admin-dash-share-hint">share_all 已开的笔记本</p>
        </section>
      </div>

      <div className="admin-dash-row-2">
        <Panel title="模型调用" hint="近 7 日趋势 · 点芯片高亮对应曲线">
          <div className="admin-dash-chips" role="tablist" aria-label="调用类型">
            <button
              type="button"
              role="tab"
              aria-selected={focus === "all"}
              className={cn("admin-dash-chip", focus === "all" && "is-active")}
              onClick={() => setFocus("all")}
            >
              全部
            </button>
            {SERIES.map((s) => {
              const call = callByKey[s.key];
              const empty = call.unavailable || call.count == null;
              return (
                <button
                  key={s.key}
                  type="button"
                  role="tab"
                  aria-selected={focus === s.key}
                  title={empty ? call.reason ?? "暂无数据" : undefined}
                  className={cn(
                    "admin-dash-chip",
                    focus === s.key && "is-active",
                    empty && "is-empty",
                  )}
                  style={
                    {
                      "--chip-color": s.color,
                    } as CSSProperties
                  }
                  onClick={() => setFocus(s.key)}
                >
                  <span className="admin-dash-chip-dot" style={{ background: s.color }} />
                  <span className="admin-dash-chip-label">{s.label}</span>
                  <span className="admin-dash-chip-count tabular-nums">
                    {empty ? "—" : fmtNum(call.count)}
                  </span>
                </button>
              );
            })}
          </div>
          <MultiLineChart days={data.model_calls.trend_7d} focus={focus} />
        </Panel>

        <Panel
          title="Token 消耗"
          hint="prompt + completion · 悬停柱看精确值"
          action={
            <span className={cn("admin-dash-pill", data.tokens.unavailable ? "is-muted" : "is-ok")}>
              {data.tokens.unavailable ? "暂无数据" : "已统计"}
            </span>
          }
        >
          <div
            className={cn(
              "admin-dash-token-hero tabular-nums",
              data.tokens.unavailable && "is-empty",
            )}
          >
            {data.tokens.unavailable ? "—" : fmtTokens(data.tokens.total)}
          </div>
          <p className="admin-dash-token-sub">
            {data.tokens.reason ?? "累计 Token（全量）"}
          </p>
          <div className="admin-dash-chart-caption">
            <span>近 7 日</span>
          </div>
          <TokenBars
            days={data.tokens.trend_7d.map((d) => ({ date: d.date, tokens: d.tokens }))}
          />
        </Panel>
      </div>

      <div className="admin-dash-row-3">
        <Panel title="队列" hint="Celery Redis 深度">
          <div className="admin-dash-queue-hero">
            <div className="admin-dash-queue-big">
              <span className="admin-dash-queue-name">media</span>
              <strong className="tabular-nums">
                {data.queues.media_depth == null ? "—" : fmtNum(data.queues.media_depth)}
              </strong>
            </div>
            <div className="admin-dash-queue-big">
              <span className="admin-dash-queue-name">studio</span>
              <strong className="tabular-nums">
                {data.queues.studio_depth == null ? "—" : fmtNum(data.queues.studio_depth)}
              </strong>
            </div>
          </div>
          <div className="admin-dash-queue-meta">
            <span>索引积压 {fmtNum(data.queues.index_backlog)}</span>
            <span className="admin-dash-dot" aria-hidden />
            <span>Studio 排队 {fmtNum(data.queues.studio_queued)}</span>
          </div>
          {!data.queues.redis_ok ? (
            <p className="admin-dash-warn">
              <AlertTriangle className="h-3 w-3 shrink-0" />
              Redis 不可用，深度暂读不到
              {data.queues.redis_error ? `：${data.queues.redis_error}` : ""}
            </p>
          ) : null}
        </Panel>

        <Panel title="就绪" hint="字幕 / 概览 / 向量">
          <div className="admin-dash-complete">
            <div className="admin-dash-complete-label">完整就绪笔记本</div>
            <div className="admin-dash-complete-value tabular-nums">
              {data.readiness.complete_notebooks.ready}
              <span>/{data.readiness.complete_notebooks.total}</span>
            </div>
            <div className="admin-dash-complete-hint">
              有来源 · 字幕+概览 ready · 索引 ready
            </div>
          </div>
          <div className="admin-dash-rings">
            <RateRing label="字幕" rate={data.readiness.subtitle} />
            <RateRing label="概览" rate={data.readiness.overview} />
            <RateRing label="向量" rate={data.readiness.vector} />
          </div>
        </Panel>

        <Panel title="失败 TOP" hint={`近 ${data.failures.window_hours} 小时`}>
          {data.failures.note ? (
            <p className="admin-dash-fail-note">{data.failures.note}</p>
          ) : null}
          {data.failures.top.length === 0 ? (
            <div className="admin-dash-chart-empty admin-dash-fail-empty">暂无失败</div>
          ) : (
            <ul className="admin-dash-fail-list">
              {data.failures.top.map((item) => (
                <li key={item.stage}>
                  <div className="admin-dash-fail-row">
                    <span>{item.label || item.stage}</span>
                    <span className="tabular-nums">{item.count}</span>
                  </div>
                  <div className="admin-dash-fail-track">
                    <div
                      className="admin-dash-fail-fill"
                      style={{ width: `${(item.count / maxFail) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

export default AdminDashboard;
