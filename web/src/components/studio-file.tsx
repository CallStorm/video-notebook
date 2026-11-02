import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function StudioFile({
  access,
  taskId,
  title,
  artifactId,
  filename,
  onBack,
}: {
  access: string;
  taskId: number;
  title: string;
  artifactId: number | null;
  filename: string | null;
  onBack: () => void;
}) {
  const signed = useQuery({
    queryKey: ["studio-artifact-url", taskId, artifactId],
    queryFn: () =>
      api<{ url: string; expires_in: number }>(`/studio/tasks/${taskId}/artifacts/${artifactId}`, { access }),
    enabled: !!access && artifactId != null,
  });
  const url = signed.data?.url ?? null;
  const missing = artifactId == null;
  const failed = signed.isError;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2">
        <p className="min-w-0 text-xs text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
            产物
          </button>
          <span className="px-1">›</span>
          <span className="text-foreground">{title}</span>
        </p>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="返回产物" onClick={onBack}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </header>
      <div className="flex flex-col items-start gap-3 p-4">
        {missing ? <p className="text-sm text-muted-foreground">没有可下载的文件</p> : null}
        {failed ? (
          <>
            <p className="text-sm text-destructive">下载地址获取失败</p>
            <Button type="button" variant="outline" onClick={() => void signed.refetch()}>
              重试
            </Button>
          </>
        ) : null}
        {!missing && !failed && url ? (
          <Button asChild>
            <a href={url} download={filename || undefined}>
              下载 {filename || title}
            </a>
          </Button>
        ) : null}
        {!missing && !failed && !url ? <Button disabled>正在获取下载地址…</Button> : null}
      </div>
    </div>
  );
}
