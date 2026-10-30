import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TagRow {
  id: number;
  name: string;
  color: string | null;
  notebook_count?: number;
}

export function EditNotebookTagsDialog({
  open,
  access,
  notebookId,
  notebookTitle,
  onClose,
}: {
  open: boolean;
  access: string;
  notebookId: number;
  notebookTitle: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const tags = useQuery({
    queryKey: ["tags"],
    queryFn: () => api<TagRow[]>("/tags", { access }),
    enabled: open && !!access,
  });

  const membership = useQuery({
    queryKey: ["notebook-tags", notebookId],
    queryFn: () =>
      api<{ tag_ids: number[] }>(`/notebooks/${notebookId}/tags`, { access }),
    enabled: open && !!access,
  });

  useEffect(() => {
    if (!open) return;
    setError(null);
    setCreating(false);
    setNewName("");
    if (membership.data) setSelected(new Set(membership.data.tag_ids));
  }, [open, membership.data]);

  const createOne = useMutation({
    mutationFn: async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) throw new Error("名称不能为空");
      return api<TagRow>("/tags", {
        method: "POST",
        access,
        body: { name: trimmed },
      });
    },
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["tags"] });
      setSelected((prev) => new Set(prev).add(created.id));
      setCreating(false);
      setNewName("");
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "创建失败"),
  });

  const save = useMutation({
    mutationFn: async () => {
      await api(`/notebooks/${notebookId}/tags`, {
        method: "PUT",
        access,
        body: { tag_ids: [...selected] },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags"] });
      qc.invalidateQueries({ queryKey: ["notebooks"] });
      qc.invalidateQueries({ queryKey: ["notebook-tags", notebookId] });
      onClose();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "保存失败"),
  });

  if (!open) return null;

  const rows = tags.data ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">编辑标签</h2>
            <p className="truncate text-xs text-muted-foreground">{notebookTitle}</p>
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

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
          {tags.isLoading || membership.isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">加载中…</p>
          ) : rows.length === 0 && !creating ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              还没有标签，先新建一个
            </p>
          ) : (
            <ul className="space-y-1">
              {rows.map((t) => {
                const checked = selected.has(t.id);
                return (
                  <li key={t.id}>
                    <label className="flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-muted/50">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-border"
                        checked={checked}
                        onChange={() => {
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(t.id)) next.delete(t.id);
                            else next.add(t.id);
                            return next;
                          });
                        }}
                      />
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: t.color || "#2F6B4F" }}
                      />
                      <span className="text-sm font-medium">{t.name}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}

          {creating ? (
            <div className="mt-3 flex gap-2 px-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="新标签名称"
                className="h-9"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newName.trim()) createOne.mutate(newName);
                }}
              />
              <Button
                size="sm"
                className="rounded-full"
                disabled={!newName.trim() || createOne.isPending}
                onClick={() => createOne.mutate(newName)}
              >
                {createOne.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "添加"
                )}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setCreating(false);
                  setNewName("");
                }}
              >
                取消
              </Button>
            </div>
          ) : (
            <button
              type="button"
              className="mt-3 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-primary hover:bg-primary/5"
              onClick={() => setCreating(true)}
            >
              <Plus className="h-4 w-4" />
              新建标签
            </button>
          )}
        </div>

        {error ? (
          <p className="border-t px-5 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <footer className="flex justify-end gap-2 border-t px-5 py-3">
          <Button variant="ghost" onClick={onClose} disabled={save.isPending}>
            取消
          </Button>
          <Button
            className="rounded-full px-5"
            disabled={save.isPending || membership.isLoading}
            onClick={() => save.mutate()}
          >
            {save.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                保存中…
              </>
            ) : (
              "保存"
            )}
          </Button>
        </footer>
      </div>
    </div>
  );
}
