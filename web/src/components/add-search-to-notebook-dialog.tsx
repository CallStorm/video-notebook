import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export interface SearchVideoRef {
  title: string;
  url: string;
}

interface Notebook {
  id: number;
  title: string;
  icon: string | null;
}

interface NotebookListResponse {
  items: Notebook[];
  total: number;
}

interface AddSearchToNotebookDialogProps {
  open: boolean;
  video: SearchVideoRef | null;
  onOpenChange: (open: boolean) => void;
  onAdded?: (notebookId: number) => void;
}

export function AddSearchToNotebookDialog({
  open,
  video,
  onOpenChange,
  onAdded,
}: AddSearchToNotebookDialogProps) {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();
  const [mode, setMode] = useState<"pick" | "create">("pick");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["notebooks", ""],
    queryFn: () => api<NotebookListResponse>("/notebooks?size=100", { access: token }),
    enabled: open && !!token,
  });

  const notebooks = useMemo(() => list.data?.items ?? [], [list.data]);

  const addMutation = useMutation({
    mutationFn: async () => {
      if (!video) throw new Error("无视频");
      let notebookId = selectedId;
      if (mode === "create") {
        const title = newTitle.trim() || video.title.slice(0, 80) || "未命名笔记本";
        const nb = await api<Notebook>("/notebooks", {
          method: "POST",
          access: token,
          body: { title, description: null, icon: "🎬" },
        });
        notebookId = nb.id;
        qc.invalidateQueries({ queryKey: ["notebooks"] });
      }
      if (!notebookId) throw new Error("请选择笔记本");
      await api(`/notebooks/${notebookId}/sources/fetch`, {
        method: "POST",
        access: token,
        body: { url: video.url },
      });
      return notebookId;
    },
    onSuccess: (notebookId) => {
      setError(null);
      onOpenChange(false);
      onAdded?.(notebookId);
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "添加失败");
    },
  });

  if (!open || !video) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-sm"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="flex w-full max-w-md flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-soft-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border/50 px-5 py-4">
          <div className="min-w-0 pr-3">
            <h2 className="text-base font-semibold tracking-tight">添加到笔记本</h2>
            <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{video.title}</p>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-8 w-8 shrink-0 rounded-full"
            onClick={() => onOpenChange(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-3.5 p-5">
          <div className="flex gap-1.5 rounded-full border border-border/60 bg-muted/30 p-1">
            <button
              type="button"
              className={cn(
                "flex-1 rounded-full px-3 py-1.5 text-sm font-medium transition",
                mode === "pick"
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setMode("pick")}
            >
              已有笔记本
            </button>
            <button
              type="button"
              className={cn(
                "flex-1 rounded-full px-3 py-1.5 text-sm font-medium transition",
                mode === "create"
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setMode("create")}
            >
              新建笔记本
            </button>
          </div>

          {mode === "pick" ? (
            <div className="max-h-64 space-y-1 overflow-y-auto rounded-2xl border border-border/60 bg-muted/15 p-2">
              {list.isLoading && (
                <p className="px-2 py-3 text-sm text-muted-foreground">加载中…</p>
              )}
              {!list.isLoading && notebooks.length === 0 && (
                <p className="px-2 py-3 text-sm text-muted-foreground">还没有笔记本，请新建</p>
              )}
              {notebooks.map((nb) => (
                <button
                  key={nb.id}
                  type="button"
                  className={cn(
                    "flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2.5 text-left text-sm transition",
                    selectedId === nb.id
                      ? "bg-accent text-foreground shadow-soft"
                      : "hover:bg-accent/55",
                  )}
                  onClick={() => setSelectedId(nb.id)}
                >
                  <span className="text-base">{nb.icon || "📁"}</span>
                  <span className="truncate font-medium">{nb.title}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-xs font-medium text-foreground" htmlFor="search-nb-title">
                笔记本名称
              </label>
              <Input
                id="search-nb-title"
                className="h-10 rounded-xl"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder={video.title.slice(0, 60) || "新笔记本"}
              />
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <footer className="flex justify-end gap-2 border-t border-border/50 px-5 py-4">
          <Button
            type="button"
            variant="ghost"
            className="rounded-full"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            className="rounded-full px-5"
            disabled={
              addMutation.isPending || (mode === "pick" && !selectedId && notebooks.length > 0)
            }
            onClick={() => addMutation.mutate()}
          >
            {addMutation.isPending ? "添加中…" : "添加并抓取"}
          </Button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
