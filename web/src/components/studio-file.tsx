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

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2">
        <p className="min-w-0 text-xs text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
            Studio
          </button>
          <span className="px-1">›</span>
          <span className="text-foreground">{title}</span>
        </p>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="返回 Studio" onClick={onBack}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </header>
      <div className="p-4">
        {url ? (
          <Button asChild>
            <a href={url} download={filename || undefined}>
              下载
            </a>
          </Button>
        ) : (
          <Button disabled>下载</Button>
        )}
      </div>
    </div>
  );
}
