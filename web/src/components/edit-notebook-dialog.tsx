import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Sparkles, X } from "lucide-react";
import { formatDateZh } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GeneratedCover } from "@/components/generated-cover";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { encodeCoverVariant, isRemoteCover } from "@/lib/cover-gen";
import { generateCover } from "@/lib/generate-cover";

interface NotebookForEdit {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
  cover_url?: string | null;
  source_count?: number;
  note_count?: number;
  updated_at?: string | null;
}

interface EditNotebookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebook: NotebookForEdit | null;
  onSubmit: (data: {
    title: string;
    description: string;
    cover_url: string | null;
  }) => void;
  isPending?: boolean;
  error?: { code: string; message: string } | null;
}

export function EditNotebookDialog({
  open,
  onOpenChange,
  notebook,
  onSubmit,
  isPending,
  error,
}: EditNotebookDialogProps) {
  const { access } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [genPending, setGenPending] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    if (open && notebook) {
      setTitle(notebook.title);
      setDescription(notebook.description ?? "");
      setCoverUrl(
        notebook.cover_url ?? encodeCoverVariant(notebook.id % 12),
      );
      setGenError(null);
      setGenPending(false);
    }
  }, [open, notebook]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open || !notebook) return null;

  const previewMeta = [
    formatDateZh(notebook.updated_at),
    (notebook.source_count ?? 0) === 1
      ? "1 个来源"
      : `${notebook.source_count ?? 0} 个来源`,
  ].join(" · ");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = title.trim();
    if (!t) return;
    onSubmit({
      title: t,
      description: description.trim(),
      cover_url: coverUrl,
    });
  };

  async function onGenerateCover() {
    if (!access || !title.trim() || genPending) return;
    setGenPending(true);
    setGenError(null);
    try {
      const result = await generateCover(access, title.trim(), description.trim());
      setCoverUrl(result.cover_url);
    } catch (err) {
      setGenError(err instanceof ApiError ? err.message : "生成失败，请重试");
    } finally {
      setGenPending(false);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <form
        className="flex max-h-[min(90vh,720px)] w-full max-w-2xl flex-col overflow-hidden rounded-xl border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <header className="flex shrink-0 items-center justify-between border-b px-5 py-3.5">
          <h2 className="text-base font-semibold">编辑笔记本</h2>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
            {/* 左侧封面 */}
            <aside className="flex w-full shrink-0 flex-col items-center gap-3 sm:w-[9.5rem]">
              <div className="book-front relative w-[8.5rem] overflow-hidden shadow-md sm:w-full">
                {isRemoteCover(coverUrl) ? (
                  <img
                    src={coverUrl!}
                    alt=""
                    className="aspect-[5/7] w-full object-cover"
                  />
                ) : (
                  <GeneratedCover
                    title={title.trim() || notebook.title}
                    coverUrl={coverUrl}
                    variant={notebook.id}
                    meta={previewMeta}
                    className="h-full w-full"
                  />
                )}
                {genPending ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs text-white backdrop-blur-[1px]">
                    AI 生成中…
                  </div>
                ) : null}
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 w-full rounded-full"
                disabled={!title.trim() || genPending || !access}
                onClick={() => void onGenerateCover()}
              >
                <Sparkles className="h-3.5 w-3.5" />
                {genPending ? "生成中…" : "生成封面"}
              </Button>
              <p className="text-center text-[11px] leading-snug text-muted-foreground">
                点击后由 AI 根据名称与描述生成
              </p>
              {genError ? (
                <p className="text-center text-xs text-destructive">{genError}</p>
              ) : null}
            </aside>

            {/* 右侧表单 */}
            <div className="min-w-0 flex-1 space-y-4">
              <div className="space-y-2">
                <label htmlFor="nb-edit-title" className="text-sm font-medium">
                  名称 <span className="text-destructive">*</span>
                </label>
                <Input
                  id="nb-edit-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={255}
                  required
                  autoFocus
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="nb-edit-desc" className="text-sm font-medium">
                  描述
                </label>
                <textarea
                  id="nb-edit-desc"
                  placeholder="简单描述（可选，生成封面时会参考）"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={2000}
                  rows={8}
                  className="flex min-h-[10rem] w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <p className="text-xs text-muted-foreground">
                  {description.length} / 2000
                </p>
              </div>

              {error && (
                <p className="text-sm text-destructive">
                  {error.code}: {error.message}
                </p>
              )}
            </div>
          </div>
        </div>

        <footer className="flex shrink-0 items-center justify-end gap-2 border-t bg-background px-5 py-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button type="submit" disabled={isPending || !title.trim() || genPending}>
            {isPending ? "保存中…" : "保存"}
          </Button>
        </footer>
      </form>
    </div>,
    document.body,
  );
}
