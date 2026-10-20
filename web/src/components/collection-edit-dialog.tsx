import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Sparkles, X } from "lucide-react";
import { GeneratedCover } from "@/components/generated-cover";
import { generateCover } from "@/lib/generate-cover";
import { isRemoteCover } from "@/lib/cover-gen";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface NotebookItem {
  id: number;
  title: string;
  icon: string | null;
}

interface CollectionDetail {
  id: number;
  name: string;
  icon: string | null;
  cover_url?: string | null;
  notebooks: NotebookItem[];
}

export function CollectionEditDialog({
  open,
  mode,
  collectionId,
  access,
  onClose,
  onSaved,
}: {
  open: boolean;
  mode: "create" | "edit";
  collectionId: number | null;
  access: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [coverPending, setCoverPending] = useState(false);
  const [coverError, setCoverError] = useState<string | null>(null);

  const notebooks = useQuery({
    queryKey: ["notebooks", ""],
    queryFn: () =>
      api<{ items: NotebookItem[] }>("/notebooks?search=&page=1&size=100", { access }),
    enabled: open && !!access,
  });

  const detail = useQuery({
    queryKey: ["collection", collectionId],
    queryFn: () => api<CollectionDetail>(`/collections/${collectionId}`, { access }),
    enabled: open && mode === "edit" && collectionId != null && !!access,
  });

  useEffect(() => {
    if (!open) return;
    setError(null);
    setCoverError(null);
    setCoverPending(false);
    setSearch("");
    if (mode === "create") {
      setName("");
      setCoverUrl(null);
      setSelected(new Set());
      return;
    }
    if (detail.data) {
      setName(detail.data.name);
      setCoverUrl(detail.data.cover_url ?? null);
      setSelected(new Set(detail.data.notebooks.map((n) => n.id)));
    }
  }, [open, mode, detail.data]);

  const items = notebooks.data?.items ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => item.title.toLowerCase().includes(q));
  }, [items, search]);

  const save = useMutation({
    mutationFn: async () => {
      const trimmed = name.trim();
      if (!trimmed) throw new Error("名称不能为空");
      const notebook_ids = [...selected];
      if (mode === "create") {
        const created = await api<{ id: number }>("/collections", {
          method: "POST",
          access,
          body: { name: trimmed, cover_url: coverUrl },
        });
        await api(`/collections/${created.id}/notebooks`, {
          method: "PUT",
          access,
          body: { notebook_ids },
        });
        return;
      }
      if (collectionId == null) throw new Error("集合不存在");
      await api(`/collections/${collectionId}`, {
        method: "PATCH",
        access,
        body: { name: trimmed, cover_url: coverUrl ?? "" },
      });
      await api(`/collections/${collectionId}/notebooks`, {
        method: "PUT",
        access,
        body: { notebook_ids },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      if (collectionId != null) qc.invalidateQueries({ queryKey: ["collection", collectionId] });
      onSaved();
      onClose();
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "保存失败");
    },
  });

  async function onGenerateCover() {
    if (!access || !name.trim() || coverPending) return;
    setCoverPending(true);
    setCoverError(null);
    try {
      const result = await generateCover(access, name.trim());
      setCoverUrl(result.cover_url);
    } catch (err) {
      setCoverError(err instanceof ApiError ? err.message : "生成封面失败");
    } finally {
      setCoverPending(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 pt-5">
          <h2 className="text-lg font-semibold">
            {mode === "create" ? "新建集合" : "编辑集合"}
          </h2>
          <button type="button" className="rounded-full bg-muted p-1.5" onClick={onClose} title="关闭">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <label className="block space-y-1.5 text-sm">
            <span className="font-medium">
              集合名称<span className="text-destructive">*</span>
            </span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="名称会用于生成封面"
              autoFocus
            />
          </label>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div>
                <span className="text-sm font-medium">集合封面</span>
                <p className="text-[11px] text-muted-foreground">按上方名称生成，不同名称配色与字标不同</p>
              </div>
              <div className="flex items-center gap-1.5">
                {coverUrl ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-8 rounded-full text-xs"
                    onClick={() => setCoverUrl(null)}
                  >
                    清除封面
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-full"
                  disabled={!name.trim() || coverPending || !access}
                  onClick={() => void onGenerateCover()}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {coverPending ? "生成中…" : "生成封面"}
                </Button>
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-border/70 bg-muted/30">
              <div className="collection-cover relative w-full">
                {coverUrl ? (
                  isRemoteCover(coverUrl) ? (
                    <img src={coverUrl} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <GeneratedCover
                      title={name.trim() || "集合"}
                      coverUrl={coverUrl}
                      variant={(collectionId ?? 0) % 12}
                      className="h-full w-full"
                    />
                  )
                ) : (
                  <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-primary/5 via-card to-[hsl(258_78%_96%)] px-3 text-center">
                    <span className="text-sm font-medium text-foreground/70">
                      {name.trim() || "先填写名称"}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      未设置封面时显示笔记本拼贴
                    </span>
                  </div>
                )}
                {coverPending ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs text-white backdrop-blur-[1px]">
                    AI 生成中…
                  </div>
                ) : null}
              </div>
            </div>
            {coverError ? <p className="text-xs text-destructive">{coverError}</p> : null}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between text-sm text-muted-foreground">
              <span>笔记本 · {selected.size} 本</span>
            </div>
            <div className="relative mb-2">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="搜索笔记本…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="max-h-64 overflow-y-auto rounded-xl border">
              {filtered.map((item) => {
                const checked = selected.has(item.id);
                return (
                  <label
                    key={item.id}
                    className="flex cursor-pointer items-center gap-3 border-b px-3 py-2.5 last:border-b-0 hover:bg-muted/40"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm">{item.title}</span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (next.has(item.id)) next.delete(item.id);
                          else next.add(item.id);
                          return next;
                        });
                      }}
                    />
                  </label>
                );
              })}
              {filtered.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs text-muted-foreground">没有笔记本</p>
              ) : null}
            </div>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>
        <footer className="flex justify-end gap-2 border-t px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            className="rounded-full bg-foreground px-5 text-background hover:bg-foreground/90"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            保存
          </Button>
        </footer>
      </div>
    </div>
  );
}
