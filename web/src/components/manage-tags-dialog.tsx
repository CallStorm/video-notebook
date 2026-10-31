import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface TagRow {
  id: number;
  name: string;
  color: string | null;
  notebook_count: number;
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

export function ManageTagsDialog({
  open,
  access,
  onClose,
}: {
  open: boolean;
  access: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  const tags = useQuery({
    queryKey: ["tags"],
    queryFn: () => api<TagRow[]>("/tags", { access }),
    enabled: open && !!access,
  });

  useEffect(() => {
    if (!open) return;
    setName("");
    setColor(COLORS[0]);
    setError(null);
    setEditingId(null);
  }, [open]);

  const create = useMutation({
    mutationFn: () =>
      api<TagRow>("/tags", {
        method: "POST",
        access,
        body: { name: name.trim(), color },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags"] });
      setName("");
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "创建失败"),
  });

  const rename = useMutation({
    mutationFn: ({ id, next }: { id: number; next: string }) =>
      api<TagRow>(`/tags/${id}`, {
        method: "PATCH",
        access,
        body: { name: next.trim() },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags"] });
      qc.invalidateQueries({ queryKey: ["notebooks"] });
      setEditingId(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "重命名失败"),
  });

  const remove = useMutation({
    mutationFn: (id: number) =>
      api(`/tags/${id}`, { method: "DELETE", access, raw: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tags"] });
      qc.invalidateQueries({ queryKey: ["notebooks"] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "删除失败"),
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
          <div>
            <h2 className="text-lg font-semibold">管理标签</h2>
            <p className="text-xs text-muted-foreground">手动创建、改名或删除标签</p>
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

        <div className="space-y-3 border-b px-5 py-4">
          <label className="text-xs font-medium text-muted-foreground">新建标签</label>
          <div className="flex gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="标签名称"
              className="h-9"
              onKeyDown={(e) => {
                if (e.key === "Enter" && name.trim()) create.mutate();
              }}
            />
            <Button
              className="rounded-full px-4"
              disabled={!name.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Plus className="h-4 w-4" />
                  <span className="ml-1">创建</span>
                </>
              )}
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                className={`h-6 w-6 rounded-full ring-offset-2 ${
                  color === c ? "ring-2 ring-foreground" : ""
                }`}
                style={{ backgroundColor: c }}
                onClick={() => setColor(c)}
                title={c}
              />
            ))}
          </div>
        </div>

        <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {tags.isLoading ? (
            <li className="px-2 py-6 text-center text-sm text-muted-foreground">加载中…</li>
          ) : rows.length === 0 ? (
            <li className="px-2 py-6 text-center text-sm text-muted-foreground">
              还没有标签，先新建一个
            </li>
          ) : (
            rows.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-2 rounded-xl px-2 py-2 hover:bg-muted/50"
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: t.color || COLORS[0] }}
                />
                {editingId === t.id ? (
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="h-8 flex-1 text-sm"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && editName.trim()) {
                        rename.mutate({ id: t.id, next: editName });
                      }
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    onBlur={() => {
                      if (editName.trim() && editName.trim() !== t.name) {
                        rename.mutate({ id: t.id, next: editName });
                      } else {
                        setEditingId(null);
                      }
                    }}
                  />
                ) : (
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left text-sm font-medium"
                    onClick={() => {
                      setEditingId(t.id);
                      setEditName(t.name);
                    }}
                    title="点击改名"
                  >
                    {t.name}
                  </button>
                )}
                <span className="shrink-0 text-[11px] text-muted-foreground">
                  {t.notebook_count} 本
                </span>
                <button
                  type="button"
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  title="删除标签"
                  onClick={() => {
                    if (confirm(`删除标签「${t.name}」？关联会一并清除。`)) {
                      remove.mutate(t.id);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))
          )}
        </ul>

        {error ? (
          <p className="border-t px-5 py-2 text-sm text-destructive">{error}</p>
        ) : null}

        <footer className="flex justify-end border-t px-5 py-3">
          <Button variant="ghost" onClick={onClose}>
            完成
          </Button>
        </footer>
      </div>
    </div>
  );
}
