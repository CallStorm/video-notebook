import { useMemo, useRef, useState } from "react";
import { Download, Maximize2, Minimize2, RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export type ComicPanel = {
  label: string;
  caption: string;
  dialogue?: string;
  scene?: string;
};

export type ComicPayload = {
  title?: string;
  panels?: ComicPanel[];
};

const PANEL_ORDER = ["误区", "冲突", "例子", "结论"] as const;

const PANEL_TONE: Record<string, { bar: string; badge: string; bubble: string }> = {
  误区: { bar: "bg-rose-500", badge: "bg-rose-100 text-rose-800", bubble: "bg-rose-50 border-rose-200" },
  冲突: { bar: "bg-amber-500", badge: "bg-amber-100 text-amber-900", bubble: "bg-amber-50 border-amber-200" },
  例子: { bar: "bg-sky-500", badge: "bg-sky-100 text-sky-900", bubble: "bg-sky-50 border-sky-200" },
  结论: { bar: "bg-emerald-500", badge: "bg-emerald-100 text-emerald-900", bubble: "bg-emerald-50 border-emerald-200" },
};

function parseComic(text: string | null | undefined): ComicPayload | null {
  if (!text || !text.trim()) return null;
  try {
    const data = JSON.parse(text) as ComicPayload;
    if (!data || typeof data !== "object") return null;
    return data;
  } catch {
    return null;
  }
}

function orderedPanels(payload: ComicPayload | null): ComicPanel[] {
  const raw = payload?.panels ?? [];
  const byLabel = new Map<string, ComicPanel>();
  for (const panel of raw) {
    if (panel && typeof panel.label === "string") byLabel.set(panel.label, panel);
  }
  return PANEL_ORDER.map((label, index) => {
    const found = byLabel.get(label) ?? raw[index];
    return {
      label,
      caption: (found?.caption || "").trim() || "（暂无文案）",
      dialogue: (found?.dialogue || "").trim(),
      scene: (found?.scene || "").trim(),
    };
  });
}

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildPrintableHtml(title: string, panels: ComicPanel[]): string {
  const cells = panels
    .map((panel) => {
      const dialogue = panel.dialogue
        ? `<div style="margin-top:8px;padding:8px 10px;border-radius:12px;background:#fff;border:1px solid #e5e7eb;font-size:13px;">💬 ${escapeHtml(panel.dialogue)}</div>`
        : "";
      const scene = panel.scene
        ? `<div style="margin-top:6px;font-size:11px;color:#6b7280;">场景：${escapeHtml(panel.scene)}</div>`
        : "";
      return `<div style="border:1px solid #e5e7eb;border-radius:16px;padding:14px;background:#fafafa;min-height:180px;">
        <div style="display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;background:#eef2ff;color:#3730a3;margin-bottom:8px;">${escapeHtml(panel.label)}</div>
        <div style="font-size:14px;line-height:1.55;color:#111827;">${escapeHtml(panel.caption)}</div>
        ${dialogue}${scene}
      </div>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"/><title>${escapeHtml(title)}</title>
  <style>body{font-family:ui-sans-serif,system-ui,sans-serif;padding:24px;color:#111}h1{font-size:20px;margin:0 0 16px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media print{.noprint{display:none}}</style></head>
  <body><button class="noprint" onclick="window.print()">打印 / 另存 PDF</button>
  <h1>${escapeHtml(title)}</h1><div class="grid">${cells}</div></body></html>`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function StudioComic({
  title,
  crumb,
  text,
  notice,
  noticeError,
  regenerating,
  expanded,
  onBack,
  onToggleExpanded,
  onRegenerate,
}: {
  title: string;
  crumb: string;
  text: string | null;
  notice: string | null;
  noticeError?: boolean;
  regenerating?: boolean;
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
  onRegenerate?: () => void;
}) {
  const payload = useMemo(() => parseComic(text), [text]);
  const panels = useMemo(() => orderedPanels(payload), [payload]);
  const gridRef = useRef<HTMLDivElement>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const displayTitle = (payload?.title || title || "四格漫").trim();
  const shell = expanded
    ? "fixed inset-0 z-40 flex flex-col bg-background"
    : "flex min-h-0 flex-1 flex-col bg-background";

  function exportJson() {
    const raw = text?.trim()
      ? text
      : JSON.stringify({ title: displayTitle, panels }, null, 2);
    downloadText(`${displayTitle || "四格漫"}.json`, raw + (raw.endsWith("\n") ? "" : "\n"), "application/json;charset=utf-8");
    setExportOpen(false);
  }

  function exportHtml() {
    const html = buildPrintableHtml(displayTitle, panels);
    downloadText(`${displayTitle || "四格漫"}.html`, html, "text/html;charset=utf-8");
    setExportOpen(false);
  }

  return (
    <div className={shell}>
      <header className="flex items-center gap-2 border-b border-border/70 px-3 py-2">
        <button
          type="button"
          className="truncate text-left text-xs text-muted-foreground hover:text-foreground"
          onClick={onBack}
          title="返回产物"
        >
          产物
          <span className="mx-1 text-border">/</span>
          <span className="text-foreground">{crumb}</span>
        </button>
        <div className="ml-auto flex items-center gap-1">
          {onRegenerate ? (
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1 rounded-full px-3 text-xs"
              disabled={regenerating}
              onClick={onRegenerate}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? "animate-spin" : ""}`} />
              重新生成
            </Button>
          ) : null}
          <div className="relative">
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1 rounded-full px-3 text-xs"
              onClick={() => setExportOpen((v) => !v)}
            >
              <Download className="h-3.5 w-3.5" />
              导出
            </Button>
            {exportOpen ? (
              <div className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-xl border border-border bg-background shadow-lg">
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-xs hover:bg-muted"
                  onClick={exportJson}
                >
                  下载 JSON
                </button>
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-xs hover:bg-muted"
                  onClick={exportHtml}
                >
                  下载 HTML（可打印）
                </button>
              </div>
            ) : null}
          </div>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 rounded-full"
            title={expanded ? "退出全屏" : "全屏"}
            onClick={onToggleExpanded}
          >
            {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8 rounded-full" title="关闭" onClick={onBack}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="border-b border-border/60 px-4 py-3">
        <h2 className="text-base font-semibold tracking-tight">{displayTitle}</h2>
        <p className="mt-0.5 text-[11px] text-muted-foreground">标准四格 · 误区 → 冲突 → 例子 → 结论</p>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3 sm:p-4">
        {notice ? (
          <div
            className={`rounded-xl border px-3 py-6 text-center text-sm ${
              noticeError ? "border-destructive/30 bg-destructive/5 text-destructive" : "border-border bg-muted/40 text-muted-foreground"
            }`}
          >
            {notice}
          </div>
        ) : (
          <div ref={gridRef} className="mx-auto grid max-w-3xl grid-cols-1 gap-3 sm:grid-cols-2">
            {panels.map((panel) => {
              const tone = PANEL_TONE[panel.label] ?? PANEL_TONE["误区"];
              return (
                <article
                  key={panel.label}
                  className="overflow-hidden rounded-2xl border border-border/80 bg-card shadow-sm"
                >
                  <div className={`h-1.5 w-full ${tone.bar}`} />
                  <div className="space-y-2.5 p-3.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone.badge}`}>
                        {panel.label}
                      </span>
                      <span className="text-[10px] text-muted-foreground">角色占位</span>
                    </div>
                    <div className="flex h-16 items-center justify-center rounded-xl bg-muted/50 text-3xl">
                      {panel.label === "误区"
                        ? "😕"
                        : panel.label === "冲突"
                          ? "⚡"
                          : panel.label === "例子"
                            ? "🎬"
                            : "✅"}
                    </div>
                    <p className="text-[13px] font-medium leading-relaxed text-foreground">{panel.caption}</p>
                    {panel.dialogue ? (
                      <div className={`rounded-2xl border px-3 py-2 text-[12px] leading-relaxed text-foreground/90 ${tone.bubble}`}>
                        <span className="mr-1 opacity-70">💬</span>
                        {panel.dialogue}
                      </div>
                    ) : null}
                    {panel.scene ? (
                      <p className="text-[10px] text-muted-foreground">场景：{panel.scene}</p>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
