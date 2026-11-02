export interface NotebookReadiness {
  subtitle_ready?: number;
  subtitle_failed?: number;
  subtitle_processing?: number;
  subtitle_total?: number;
  subtitle_error?: string | null;
  overview_ready?: number;
  overview_failed?: number;
  overview_processing?: number;
  overview_total?: number;
  overview_error?: string | null;
  index_status?: string | null;
  index_error?: string | null;
  index_stale_reason?: string | null;
}

type Tone = "muted" | "ok" | "warn" | "bad" | "run";

export interface StatusPart {
  text: string;
  tone: Tone;
}

export interface NotebookStatusLine {
  parts: StatusPart[];
  detail: { text: string; tone: "bad" | "warn" } | null;
}

const TONE_CLASS: Record<Tone, string> = {
  muted: "",
  ok: "font-medium text-emerald-700",
  warn: "font-medium text-amber-700",
  bad: "font-medium text-destructive",
  run: "font-medium text-primary",
};

function mediaPart(
  label: string,
  ready: number,
  failed: number,
  processing: number,
  total: number,
): StatusPart {
  if (failed > 0) {
    return { text: `${label} ${failed}/${total} 失败`, tone: "bad" };
  }
  if (processing > 0 && ready === 0) {
    return { text: `${label} 生成中`, tone: "run" };
  }
  if (processing > 0) {
    return { text: `${label} ${ready}/${total} 生成中`, tone: "run" };
  }
  if (ready <= 0) {
    return { text: `${label}未开始`, tone: "muted" };
  }
  return { text: `${label} ${ready}/${total}`, tone: "muted" };
}

function indexPart(nb: NotebookReadiness): StatusPart | null {
  const status = nb.index_status;
  if (!status) return null;
  if (status === "failed") return { text: "索引失败", tone: "bad" };
  if (status === "indexing") return { text: "入库中", tone: "run" };
  if (status === "ready" && nb.index_stale_reason) {
    return { text: "索引过期", tone: "warn" };
  }
  if (status === "ready") return { text: "已入库", tone: "ok" };
  return { text: "未入库", tone: "muted" };
}

function clip(text: string, limit = 40): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= limit) return flat;
  return `${flat.slice(0, limit)}…`;
}

export function notebookStatusLine(nb: NotebookReadiness): NotebookStatusLine | null {
  const hasCounts = nb.subtitle_total != null || nb.overview_total != null;
  const hasIndex = !!nb.index_status;
  if (!hasCounts && !hasIndex) return null;

  const subTotal = nb.subtitle_total ?? 0;
  const ovTotal = nb.overview_total ?? 0;
  const parts: StatusPart[] = [];
  if (subTotal === 0 && ovTotal === 0) {
    if (hasCounts) parts.push({ text: "无来源", tone: "muted" });
  } else {
    parts.push(
      mediaPart(
        "字幕",
        nb.subtitle_ready ?? 0,
        nb.subtitle_failed ?? 0,
        nb.subtitle_processing ?? 0,
        subTotal,
      ),
    );
    parts.push(
      mediaPart(
        "概览",
        nb.overview_ready ?? 0,
        nb.overview_failed ?? 0,
        nb.overview_processing ?? 0,
        ovTotal,
      ),
    );
  }
  const indexed = indexPart(nb);
  if (indexed) parts.push(indexed);
  if (parts.length === 0) return null;

  let detail: NotebookStatusLine["detail"] = null;
  if ((nb.subtitle_failed ?? 0) > 0) {
    const err = nb.subtitle_error?.trim();
    detail = { text: err ? `字幕失败：${clip(err)}` : "字幕失败", tone: "bad" };
  } else if ((nb.overview_failed ?? 0) > 0) {
    const err = nb.overview_error?.trim();
    detail = { text: err ? `概览失败：${clip(err)}` : "概览失败", tone: "bad" };
  } else if (nb.index_status === "failed") {
    const err = nb.index_error?.trim();
    detail = err ? { text: `索引失败：${clip(err)}`, tone: "bad" } : null;
  } else if (nb.index_status === "ready" && nb.index_stale_reason) {
    detail = { text: nb.index_stale_reason, tone: "warn" };
  }

  return { parts, detail };
}

export function NotebookStatusLines({
  notebook,
  size = "card",
}: {
  notebook: NotebookReadiness;
  size?: "card" | "list";
}) {
  const line = notebookStatusLine(notebook);
  if (!line) return null;
  const text = size === "list" ? "text-xs" : "text-[10px]";
  return (
    <div className="min-w-0">
      <p className={`flex flex-wrap items-center leading-snug text-muted-foreground ${text}`}>
        {line.parts.map((part, index) => (
          <span key={`${part.text}-${index}`}>
            {index > 0 ? <span className="text-muted-foreground/60"> · </span> : null}
            <span className={TONE_CLASS[part.tone]}>{part.text}</span>
          </span>
        ))}
      </p>
      {line.detail ? (
        <p
          className={`mt-0.5 line-clamp-2 leading-snug ${text} ${
            line.detail.tone === "warn" ? "text-amber-700" : "text-destructive"
          }`}
        >
          {line.detail.text}
        </p>
      ) : null}
    </div>
  );
}
