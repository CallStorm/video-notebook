import { useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GeneratedCover } from "@/components/generated-cover";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { EMPTY_COVER_TOKEN, isEmptyCover } from "@/lib/cover-gen";
import { generateCover } from "@/lib/generate-cover";

interface NewNotebookDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: {
    title: string;
    description: string;
    cover_url: string;
  }) => void;
  isPending?: boolean;
  error?: { code: string; message: string } | null;
}

export function NewNotebookDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
  error,
}: NewNotebookDialogProps) {
  const { access } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [coverUrl, setCoverUrl] = useState<string>(EMPTY_COVER_TOKEN);
  const [genPending, setGenPending] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genHint, setGenHint] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setCoverUrl(EMPTY_COVER_TOKEN);
      setGenError(null);
      setGenHint(null);
      setGenPending(false);
    }
  }, [open]);

  if (!open) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    onSubmit({
      title: title.trim(),
      description: description.trim(),
      cover_url: isEmptyCover(coverUrl) ? "" : coverUrl,
    });
  };

  async function onGenerateCover() {
    if (!access || !title.trim() || genPending) return;
    setGenPending(true);
    setGenError(null);
    if (!description.trim()) {
      setGenHint("填写描述后生成更贴切");
    } else {
      setGenHint(null);
    }
    try {
      const result = await generateCover(access, title.trim(), description.trim());
      setCoverUrl(result.cover_url);
    } catch (err) {
      setGenError(err instanceof ApiError ? err.message : "生成失败，请重试");
    } finally {
      setGenPending(false);
    }
  }

  return (
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

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
            <aside className="flex w-full shrink-0 flex-col items-center gap-3 sm:w-[9.5rem]">
              <div className="book-front relative w-[8.5rem] overflow-hidden shadow-md sm:w-full">
                <GeneratedCover
                  title={isEmptyCover(coverUrl) ? "" : title.trim() || "新笔记本"}
                  coverUrl={coverUrl}
                  meta="刚刚 · 0 个来源"
                  className="h-full w-full"
                />
                {genPending ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-xs text-white backdrop-blur-[1px]">
                    生成中…
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
                根据名称与描述生成封面图（需后台配置封面文生图模型）
              </p>
              {genHint && !genError ? (
                <p className="text-center text-[11px] text-amber-700 dark:text-amber-400">{genHint}</p>
              ) : null}
              {genError ? (
                <p className="text-center text-xs text-destructive">{genError}</p>
              ) : null}
            </aside>

            <div className="min-w-0 flex-1 space-y-4">
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
            {isPending ? "创建中…" : "创建"}
          </Button>
        </footer>
      </form>
    </div>
  );
}
