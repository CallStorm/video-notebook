import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EMOJI_OPTIONS = ["🎬", "📚", "🎓", "🔬", "💡", "🚀", "🎵", "📁", "🧠", "🌐"];

interface NotebookForEdit {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
}

interface EditNotebookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  notebook: NotebookForEdit | null;
  onSubmit: (data: { title: string; description: string; icon: string | null }) => void;
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
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState<string | null>(null);

  // 打开 / 切换 notebook 时同步表单
  useEffect(() => {
    if (open && notebook) {
      setTitle(notebook.title);
      setDescription(notebook.description ?? "");
      setIcon(notebook.icon);
    }
  }, [open, notebook]);

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open || !notebook) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = title.trim();
    if (!t) return;
    onSubmit({ title: t, description: description.trim(), icon });
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <form
        className="flex w-full max-w-md flex-col rounded-lg border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <header className="flex items-center justify-between border-b p-4">
          <h2 className="text-base font-semibold">Edit Notebook</h2>
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

        <div className="space-y-4 p-4">
          <div className="flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted text-4xl">
              {icon || "📁"}
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="nb-edit-title" className="text-sm font-medium">
              Notebook Title <span className="text-destructive">*</span>
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
              placeholder="简单描述（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
              rows={4}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <p className="text-xs text-muted-foreground">
              {description.length} / 2000
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">图标</label>
            <div className="flex flex-wrap gap-1">
              {EMOJI_OPTIONS.map((e) => (
                <button
                  type="button"
                  key={e}
                  onClick={() => setIcon(e)}
                  className={`rounded p-1.5 text-xl ${
                    icon === e
                      ? "bg-primary/10 ring-2 ring-primary"
                      : "hover:bg-muted"
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">
              {error.code}: {error.message}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t p-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isPending || !title.trim()}
          >
            {isPending ? "保存中…" : "Save"}
          </Button>
        </footer>
      </form>
    </div>,
    document.body,
  );
}
