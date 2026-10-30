import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Plus, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface NotebookBrief {
  id: number;
  title: string;
  description: string | null;
}

interface SuggestedTag {
  temp_id: string;
  name: string;
  color: string | null;
}

interface Assignment {
  notebook_id: number;
  tag_temp_ids: string[];
}

interface PreviewResponse {
  tags: SuggestedTag[];
  assignments: Assignment[];
  notebooks: NotebookBrief[];
  message?: string | null;
}

const COLORS = [
  "#2F6B4F",
  "#3B82F6",
  "#8B5CF6",
  "#F59E0B",
  "#EF4444",
  "#06B6D4",
  "#EC4899",
  "#84CC16",
];

function newTempId(): string {
  return `t${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export function AutoOrganizeDialog({
  open,
  access,
  onClose,
  onApplied,
}: {
  open: boolean;
  access: string;
  onClose: () => void;
  onApplied: () => void;
}) {
  const [phase, setPhase] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [notebooks, setNotebooks] = useState<NotebookBrief[]>([]);
  const [tags, setTags] = useState<SuggestedTag[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [reloadKey, setReloadKey] = useState(0);

  const loadPreview = useCallback(async () => {
    setPhase("loading");
    setError(null);
    setHint(null);
    setTags([]);
    setAssignments([]);
    setNotebooks([]);
    try {
      const data = await api<PreviewResponse>("/tags/auto-organize/preview", {
        method: "POST",
        access,
        body: {},
      });
      setNotebooks(data.notebooks ?? []);
      const nextAssignments = data.assignments ?? [];
      const used = new Set(nextAssignments.flatMap((a) => a.tag_temp_ids));
      // Hide suggested tags with zero notebook associations in the plan.
      setTags((data.tags ?? []).filter((t) => used.has(t.temp_id)));
      setAssignments(nextAssignments);
      setHint(data.message ?? null);
      if (!data.notebooks?.length) {
        setPhase("empty");
      } else {
        setPhase("ready");
      }
    } catch (err) {
      setPhase("error");
      setError(err instanceof ApiError ? err.message : "分析失败，请重试");
    }
  }, [access]);

  useEffect(() => {
    if (!open || !access) return;
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await loadPreview();
    })();
    return () => {
      cancelled = true;
    };
  }, [open, access, reloadKey, loadPreview]);

  const notebookMap = useMemo(() => {
    const m = new Map<number, NotebookBrief>();
    for (const n of notebooks) m.set(n.id, n);
    return m;
  }, [notebooks]);

  const apply = useMutation({
    mutationFn: () =>
      api<{ tags: unknown[] }>("/tags/auto-organize/apply", {
        method: "POST",
        access,
        body: {
          tags: tags.map((t) => ({
            temp_id: t.temp_id,
            name: t.name.trim(),
            color: t.color,
          })),
          assignments: assignments.map((a) => ({
            notebook_id: a.notebook_id,
            tag_temp_ids: a.tag_temp_ids,
          })),
        },
      }),
    onSuccess: () => {
      onApplied();
      onClose();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "覆盖失败，请重试");
    },
  });

  if (!open) return null;

  function renameTag(tempId: string, name: string) {
    setTags((prev) => prev.map((t) => (t.temp_id === tempId ? { ...t, name } : t)));
  }

  function removeTag(tempId: string) {
    setTags((prev) => prev.filter((t) => t.temp_id !== tempId));
    setAssignments((prev) =>
      prev.map((a) => ({
        ...a,
        tag_temp_ids: a.tag_temp_ids.filter((id) => id !== tempId),
      })),
    );
  }

  function addTag() {
    const created: SuggestedTag = {
      temp_id: newTempId(),
      name: "新标签",
      color: COLORS[tags.length % COLORS.length],
    };
    setTags((prev) => [...prev, created]);
  }

  function toggleAssignment(notebookId: number, tempId: string) {
    setAssignments((prev) =>
      prev.map((a) => {
        if (a.notebook_id !== notebookId) return a;
        const has = a.tag_temp_ids.includes(tempId);
        return {
          ...a,
          tag_temp_ids: has
            ? a.tag_temp_ids.filter((id) => id !== tempId)
            : [...a.tag_temp_ids, tempId],
        };
      }),
    );
  }

  function clearAssignment(notebookId: number) {
    setAssignments((prev) =>
      prev.map((a) =>
        a.notebook_id === notebookId ? { ...a, tag_temp_ids: [] } : a,
      ),
    );
  }

  const canApply =
    phase === "ready" &&
    tags.length > 0 &&
    tags.every((t) => t.name.trim().length > 0) &&
    !apply.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">自动整理 · 确认方案</h2>
            <p className="text-xs text-muted-foreground">
              可调整下方新建标签与每本笔记本的关联，确认后覆盖现有关联
            </p>
          </div>
          <button
            type="button"
            className="rounded-full bg-muted p-1.5"
            onClick={onClose}
            title="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {phase === "loading" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              正在分析笔记本名称与描述…
            </div>
          ) : phase === "empty" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
              <p className="text-sm font-medium">没有可整理的笔记本</p>
              <p className="text-xs text-muted-foreground">先新建几本笔记本再来自动整理。</p>
            </div>
          ) : phase === "error" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-center">
              <p className="text-sm text-destructive">{error}</p>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => setReloadKey((k) => k + 1)}
              >
                <RefreshCw className="h-4 w-4" />
                <span className="ml-1">重试</span>
              </Button>
            </div>
          ) : (
            <div className="space-y-5">
              {hint ? (
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                  {hint}
                </p>
              ) : null}

              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">将新建的标签</h3>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 rounded-full px-2 text-xs"
                    onClick={addTag}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    添加标签
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {tags.map((t) => (
                    <div
                      key={t.temp_id}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-card px-2 py-1 shadow-soft"
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: t.color || COLORS[0] }}
                      />
                      <Input
                        value={t.name}
                        onChange={(e) => renameTag(t.temp_id, e.target.value)}
                        className="h-7 w-24 border-0 bg-transparent px-1 text-xs shadow-none focus-visible:ring-0"
                      />
                      <button
                        type="button"
                        className="rounded-full p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        title="删除标签"
                        onClick={() => removeTag(t.temp_id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                  {tags.length === 0 ? (
                    <p className="text-xs text-muted-foreground">至少保留一个标签</p>
                  ) : null}
                </div>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold">关联关系</h3>
                <div className="overflow-hidden rounded-xl border border-border/70">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-muted/40 text-xs text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2 font-medium">笔记本</th>
                        <th className="px-3 py-2 font-medium">标签</th>
                        <th className="w-16 px-2 py-2" />
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {assignments.map((a) => {
                        const nb = notebookMap.get(a.notebook_id);
                        return (
                          <tr key={a.notebook_id} className="align-top">
                            <td className="px-3 py-2.5">
                              <p className="font-medium leading-snug">
                                {nb?.title ?? `笔记本 ${a.notebook_id}`}
                              </p>
                              {nb?.description ? (
                                <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
                                  {nb.description}
                                </p>
                              ) : null}
                            </td>
                            <td className="px-3 py-2.5">
                              <div className="flex flex-wrap gap-1.5">
                                {tags.map((t) => {
                                  const on = a.tag_temp_ids.includes(t.temp_id);
                                  return (
                                    <button
                                      key={t.temp_id}
                                      type="button"
                                      onClick={() =>
                                        toggleAssignment(a.notebook_id, t.temp_id)
                                      }
                                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition-colors ${
                                        on
                                          ? "border-primary/40 bg-primary/10 text-foreground"
                                          : "border-border/60 text-muted-foreground hover:bg-muted/60"
                                      }`}
                                    >
                                      <span
                                        className="h-1.5 w-1.5 rounded-full"
                                        style={{
                                          backgroundColor: t.color || COLORS[0],
                                        }}
                                      />
                                      {t.name.trim() || "未命名"}
                                    </button>
                                  );
                                })}
                              </div>
                            </td>
                            <td className="px-2 py-2.5 text-right">
                              <button
                                type="button"
                                className="text-[11px] text-muted-foreground hover:text-foreground"
                                onClick={() => clearAssignment(a.notebook_id)}
                              >
                                清空
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
        </div>

        <footer className="space-y-3 border-t px-5 py-4">
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
            确认后将用上述方案覆盖每本笔记本上的标签关联；仅会新建实际有关联的标签。确认时会清理当前没有任何笔记本关联的空标签。
          </p>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={apply.isPending}>
              取消
            </Button>
            <Button
              variant="outline"
              className="rounded-full"
              disabled={apply.isPending || phase === "loading"}
              onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="h-4 w-4" />
              <span className="ml-1">重新生成</span>
            </Button>
            <Button
              variant="destructive"
              className="rounded-full px-5"
              disabled={!canApply}
              onClick={() => apply.mutate()}
            >
              {apply.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  覆盖中…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  确认并覆盖
                </>
              )}
            </Button>
          </div>
          {error && phase === "ready" ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
