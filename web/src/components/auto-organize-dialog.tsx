import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Plus, Sparkles, Trash2, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface NotebookBrief {
  id: number;
  title: string;
  description: string | null;
}

interface SuggestedCollection {
  temp_id: string;
  name: string;
  notebook_ids: number[];
}

interface PreviewResponse {
  collections: SuggestedCollection[];
  notebooks: NotebookBrief[];
  message?: string | null;
}

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
  const [collections, setCollections] = useState<SuggestedCollection[]>([]);
  const [selectedTempId, setSelectedTempId] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !access) return;
    let cancelled = false;
    setPhase("loading");
    setError(null);
    setHint(null);
    setCollections([]);
    setNotebooks([]);
    setSelectedTempId(null);

    (async () => {
      try {
        const data = await api<PreviewResponse>("/collections/auto-organize/preview", {
          method: "POST",
          access,
          body: {},
        });
        if (cancelled) return;
        setNotebooks(data.notebooks ?? []);
        setCollections(data.collections ?? []);
        setHint(data.message ?? null);
        if (!data.notebooks?.length) {
          setPhase("empty");
        } else {
          setPhase("ready");
          setSelectedTempId(data.collections?.[0]?.temp_id ?? null);
        }
      } catch (err) {
        if (cancelled) return;
        setPhase("error");
        setError(err instanceof ApiError ? err.message : "分析失败，请重试");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, access]);

  const notebookMap = useMemo(() => {
    const m = new Map<number, NotebookBrief>();
    for (const n of notebooks) m.set(n.id, n);
    return m;
  }, [notebooks]);

  const apply = useMutation({
    mutationFn: () =>
      api<{ collections: unknown[] }>("/collections/auto-organize/apply", {
        method: "POST",
        access,
        body: {
          collections: collections.map((c) => ({
            temp_id: c.temp_id,
            name: c.name.trim(),
            notebook_ids: c.notebook_ids,
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

  function renameCollection(tempId: string, name: string) {
    setCollections((prev) =>
      prev.map((c) => (c.temp_id === tempId ? { ...c, name } : c)),
    );
  }

  function removeCollection(tempId: string) {
    setCollections((prev) => {
      const target = prev.find((c) => c.temp_id === tempId);
      if (!target) return prev;
      const rest = prev.filter((c) => c.temp_id !== tempId);
      if (target.notebook_ids.length === 0) {
        return rest;
      }
      // move notebooks into 未归类 or create it
      let uncategorized = rest.find((c) => c.name === "未归类");
      if (!uncategorized) {
        uncategorized = {
          temp_id: newTempId(),
          name: "未归类",
          notebook_ids: [...target.notebook_ids],
        };
        return [...rest, uncategorized];
      }
      return rest.map((c) =>
        c.temp_id === uncategorized!.temp_id
          ? {
              ...c,
              notebook_ids: [...c.notebook_ids, ...target.notebook_ids],
            }
          : c,
      );
    });
    setSelectedTempId((cur) => (cur === tempId ? null : cur));
  }

  function addCollection() {
    const created: SuggestedCollection = {
      temp_id: newTempId(),
      name: "新集合",
      notebook_ids: [],
    };
    setCollections((prev) => [...prev, created]);
    setSelectedTempId(created.temp_id);
  }

  function moveNotebook(notebookId: number, toTempId: string) {
    setCollections((prev) =>
      prev.map((c) => {
        const without = c.notebook_ids.filter((id) => id !== notebookId);
        if (c.temp_id === toTempId) {
          if (without.includes(notebookId) || c.notebook_ids.includes(notebookId)) {
            return { ...c, notebook_ids: [...without, notebookId] };
          }
          return { ...c, notebook_ids: [...without, notebookId] };
        }
        return { ...c, notebook_ids: without };
      }),
    );
  }

  const canApply =
    phase === "ready" &&
    collections.length > 0 &&
    collections.every((c) => c.name.trim().length > 0) &&
    !apply.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">自动整理集合</h2>
            <p className="text-xs text-muted-foreground">
              根据笔记本名称与描述生成建议，确认后整表覆盖现有集合
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

        <div className="min-h-0 flex-1 overflow-hidden">
          {phase === "loading" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              正在分析笔记本名称与描述…
            </div>
          ) : phase === "empty" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 px-6 text-center">
              <p className="text-sm font-medium">没有可整理的笔记本</p>
              <p className="text-xs text-muted-foreground">先新建几本笔记本再来自动整理。</p>
            </div>
          ) : phase === "error" ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 px-6 text-center">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          ) : (
            <div className="grid h-[min(62vh,520px)] grid-cols-1 md:grid-cols-[240px_1fr]">
              <aside className="flex min-h-0 flex-col border-b md:border-b-0 md:border-r">
                <div className="flex items-center justify-between px-4 py-3">
                  <span className="text-xs font-medium text-muted-foreground">
                    建议集合 · {collections.length}
                  </span>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 rounded-full px-2 text-xs"
                    onClick={addCollection}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    添加集合
                  </Button>
                </div>
                <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-3">
                  {collections.map((c) => {
                    const active = c.temp_id === selectedTempId;
                    return (
                      <li key={c.temp_id}>
                        <div
                          className={`rounded-xl border px-2.5 py-2 ${
                            active
                              ? "border-primary/40 bg-primary/5"
                              : "border-transparent hover:bg-muted/50"
                          }`}
                        >
                          <button
                            type="button"
                            className="mb-1 w-full text-left text-[11px] text-muted-foreground"
                            onClick={() => setSelectedTempId(c.temp_id)}
                          >
                            {c.notebook_ids.length} 本
                          </button>
                          <div className="flex items-center gap-1">
                            <Input
                              value={c.name}
                              onChange={(e) => renameCollection(c.temp_id, e.target.value)}
                              onFocus={() => setSelectedTempId(c.temp_id)}
                              className="h-8 text-sm"
                            />
                            <button
                              type="button"
                              className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                              title="删除集合"
                              onClick={() => removeCollection(c.temp_id)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </aside>

              <div className="min-h-0 overflow-y-auto px-4 py-3">
                {hint ? (
                  <p className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                    {hint}
                  </p>
                ) : null}
                <div className="space-y-4">
                  {collections.map((c) => (
                    <section key={c.temp_id} className="rounded-xl border border-border/70">
                      <header className="flex items-center justify-between border-b px-3 py-2">
                        <h3 className="text-sm font-medium">{c.name.trim() || "未命名"}</h3>
                        <span className="text-xs text-muted-foreground">
                          {c.notebook_ids.length} 本
                        </span>
                      </header>
                      <ul className="divide-y">
                        {c.notebook_ids.length === 0 ? (
                          <li className="px-3 py-4 text-center text-xs text-muted-foreground">
                            暂无笔记本（可从其他集合改归属移入）
                          </li>
                        ) : (
                          c.notebook_ids.map((nid) => {
                            const nb = notebookMap.get(nid);
                            return (
                              <li
                                key={nid}
                                className="flex items-center gap-3 px-3 py-2.5"
                              >
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-medium">
                                    {nb?.title ?? `笔记本 ${nid}`}
                                  </p>
                                  {nb?.description ? (
                                    <p className="truncate text-[11px] text-muted-foreground">
                                      {nb.description}
                                    </p>
                                  ) : null}
                                </div>
                                <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                                  <span className="hidden sm:inline">归属</span>
                                  <select
                                    className="h-8 max-w-[9rem] rounded-md border border-input bg-background px-2 text-xs"
                                    value={c.temp_id}
                                    onChange={(e) => moveNotebook(nid, e.target.value)}
                                  >
                                    {collections.map((opt) => (
                                      <option key={opt.temp_id} value={opt.temp_id}>
                                        {opt.name.trim() || "未命名"}
                                      </option>
                                    ))}
                                  </select>
                                </label>
                              </li>
                            );
                          })
                        )}
                      </ul>
                    </section>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <footer className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-relaxed text-amber-700 dark:text-amber-300">
            确认后将删除现有集合，并用下列方案覆盖。笔记本本身不会被删除。
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={apply.isPending}>
              取消
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
                  确认覆盖
                </>
              )}
            </Button>
          </div>
          {error && phase === "ready" ? (
            <p className="w-full text-sm text-destructive sm:order-last">{error}</p>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
