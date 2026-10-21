import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { GeneratedFolderIcon } from "@/components/generated-folder-icon";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Collection {
  id: number;
  name: string;
  icon: string | null;
  cover_url?: string | null;
}

export function AddToCollectionDialog({
  open,
  access,
  notebookId,
  notebookTitle,
  notebookIcon,
  onClose,
}: {
  open: boolean;
  access: string;
  notebookId: number;
  notebookTitle: string;
  notebookIcon: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: () => api<Collection[]>("/collections", { access }),
    enabled: open && !!access,
  });

  const membership = useQuery({
    queryKey: ["notebook-collections", notebookId],
    queryFn: () =>
      api<{ collection_ids: number[] }>(`/notebooks/${notebookId}/collections`, { access }),
    enabled: open && !!access,
  });

  useEffect(() => {
    if (!open) return;
    setError(null);
    setCreating(false);
    setNewName("");
    if (membership.data) setSelected(new Set(membership.data.collection_ids));
  }, [open, membership.data]);

  const createOne = useMutation({
    mutationFn: async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) throw new Error("名称不能为空");
      return api<Collection>("/collections", {
        method: "POST",
        access,
        body: { name: trimmed },
      });
    },
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      setSelected((prev) => new Set(prev).add(created.id));
      setCreating(false);
      setNewName("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "创建失败"),
  });

  const save = useMutation({
    mutationFn: async () => {
      await api(`/notebooks/${notebookId}/collections`, {
        method: "PUT",
        access,
        body: { collection_ids: [...selected] },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection"] });
      qc.invalidateQueries({ queryKey: ["notebook-collections", notebookId] });
      onClose();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "保存失败"),
  });

  if (!open) return null;

  const rows = collections.data ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 pt-5">
          <h2 className="text-lg font-semibold">Add to collection</h2>
          <button type="button" className="rounded-full bg-muted p-1.5" onClick={onClose} title="关闭">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div className="flex items-center gap-3 rounded-full bg-muted/60 px-4 py-2.5">
            <span className="text-lg">{notebookIcon || "📁"}</span>
            <span className="truncate text-sm font-medium">{notebookTitle}</span>
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Select collections ({selected.size})</span>
              <button
                type="button"
                className="text-blue-600 hover:underline"
                onClick={() => setCreating(true)}
              >
                + Create new
              </button>
            </div>
            {creating ? (
              <div className="mb-2 flex gap-2">
                <Input
                  autoFocus
                  placeholder="Collection name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") createOne.mutate(newName);
                  }}
                />
                <Button
                  className="rounded-full bg-blue-500 text-white hover:bg-blue-600"
                  disabled={createOne.isPending}
                  onClick={() => createOne.mutate(newName)}
                >
                  Add
                </Button>
              </div>
            ) : null}
            <div className="max-h-64 overflow-y-auto rounded-xl border">
              {rows.map((row) => {
                const checked = selected.has(row.id);
                return (
                  <label
                    key={row.id}
                    className="flex cursor-pointer items-center gap-3 border-b px-3 py-2.5 last:border-b-0 hover:bg-muted/40"
                  >
                    <span className="flex h-8 w-10 shrink-0 items-center justify-center">
                      <GeneratedFolderIcon
                        title={row.name}
                        coverUrl={row.cover_url}
                        variant={row.id}
                        className="h-full w-full"
                      />
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm">{row.name}</span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (next.has(row.id)) next.delete(row.id);
                          else next.add(row.id);
                          return next;
                        });
                      }}
                    />
                  </label>
                );
              })}
              {rows.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs text-muted-foreground">还没有集合</p>
              ) : null}
            </div>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>
        <footer className="flex justify-end gap-2 border-t px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            className="rounded-full bg-blue-500 px-5 text-white hover:bg-blue-600"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            Save
          </Button>
        </footer>
      </div>
    </div>
  );
}
