import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface NewNotebookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: { title: string; description: string; icon: string }) => void;
  isPending?: boolean;
  error?: { code: string; message: string } | null;
}

const EMOJI_OPTIONS = ["🎬", "📚", "🎓", "🔬", "💡", "🚀", "🎵", "📁", "🧠", "🌐"];

export function NewNotebookDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
  error,
}: NewNotebookDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState<string>(EMOJI_OPTIONS[0]);

  // 打开弹窗时重置
  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setIcon(EMOJI_OPTIONS[0]);
    }
  }, [open]);

  if (!open) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      icon,
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <form
        className="flex w-full max-w-lg flex-col rounded-lg border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <header className="flex items-center justify-between border-b p-4">
          <h2 className="text-base font-semibold">新建笔记本</h2>
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
          <div className="space-y-2">
            <label htmlFor="nb-title" className="text-sm font-medium">
              名称 <span className="text-destructive">*</span>
            </label>
            <Input
              id="nb-title"
              placeholder="给这个笔记本起个名字"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={255}
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="nb-desc" className="text-sm font-medium">
              描述
            </label>
            <textarea
              id="nb-desc"
              placeholder="简单描述这个笔记本要做什么（可选）"
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
            取消
          </Button>
          <Button type="submit" disabled={isPending || !title.trim()}>
            {isPending ? "创建中…" : "创建"}
          </Button>
        </footer>
      </form>
    </div>
  );
}
