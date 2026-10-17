import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, Minimize2, MoreVertical, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export interface SlideArtifact {
  id: number;
  role: string;
  filename: string;
  mime: string;
}

export function StudioSlides({
  access,
  taskId,
  title,
  pdfError,
  artifacts,
  pending,
  notice,
  expanded,
  onBack,
  onToggleExpanded,
}: {
  access: string;
  taskId: number;
  title: string;
  pdfError: string | null;
  artifacts: SlideArtifact[];
  pending?: boolean;
  notice?: string | null;
  expanded: boolean;
  onBack: () => void;
  onToggleExpanded: () => void;
}) {
  const main = artifacts.find((item) => item.role === "main") ?? null;
  const pdf = pdfError
    ? null
    : (artifacts.find((item) => item.role === "side" && item.mime === "application/pdf") ??
      artifacts.find((item) => item.mime === "application/pdf") ??
      null);
  const pptx = useSignedArtifact(access, taskId, main?.id ?? null);
  const pdfUrl = useSignedArtifact(access, taskId, pdf?.id ?? null);
  const previewUrl = pdfError ? null : (pdfUrl.data?.url ?? null);
  const shell = expanded
    ? "fixed inset-0 z-40 flex flex-col bg-background"
    : "flex min-h-0 flex-1 flex-col bg-background";

  let body: ReactNode;
  if (notice) {
    body = <p className="p-4 text-sm text-destructive">{notice}</p>;
  } else if (pending) {
    body = <p className="p-4 text-sm text-muted-foreground">加载预览…</p>;
  } else if (pdfError) {
    body = <p className="p-4 text-sm text-muted-foreground">预览不可用</p>;
  } else if (previewUrl) {
    body = (
      <div className="min-h-0 flex-1">
        <iframe title={title} src={previewUrl} className="h-full w-full border-0" />
      </div>
    );
  } else {
    body = <p className="p-4 text-sm text-muted-foreground">加载预览…</p>;
  }

  return (
    <div className={shell}>
      <header className="relative z-10 flex shrink-0 items-start justify-between gap-2 border-b px-3 py-2">
        <p className="min-w-0 text-xs text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onBack}>
            Studio
          </button>
          <span className="px-1">›</span>
          <span className="text-foreground">{title}</span>
        </p>
        <div className="flex shrink-0 items-center">
          <DownloadMenu
            pptxUrl={pptx.data?.url ?? null}
            pptxName={main?.filename || `${title}.pptx`}
            pdfUrl={pdfError ? null : previewUrl}
            pdfName={pdf?.filename || `${title}.pdf`}
          />
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            title={expanded ? "还原" : "铺满"}
            onClick={onToggleExpanded}
          >
            {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </Button>
          <Button size="icon" variant="ghost" className="h-7 w-7" title="返回 Studio" onClick={onBack}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>
      {body}
    </div>
  );
}

function useSignedArtifact(access: string, taskId: number, artifactId: number | null) {
  return useQuery({
    queryKey: ["studio-artifact-url", taskId, artifactId],
    queryFn: () =>
      api<{ url: string; expires_in: number }>(`/studio/tasks/${taskId}/artifacts/${artifactId}`, { access }),
    enabled: !!access && artifactId != null,
  });
}

function DownloadMenu({
  pptxUrl,
  pptxName,
  pdfUrl,
  pdfName,
}: {
  pptxUrl: string | null;
  pptxName: string;
  pdfUrl: string | null;
  pdfName: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Button
        size="icon"
        variant="ghost"
        className="h-7 w-7"
        title="更多"
        onClick={() => setOpen((value) => !value)}
      >
        <MoreVertical className="h-3.5 w-3.5" />
      </Button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-8 z-50 w-36 overflow-hidden rounded-md border bg-popover py-1 text-popover-foreground shadow-lg"
        >
          <a
            role="menuitem"
            href={pptxUrl ?? undefined}
            download={pptxUrl ? pptxName : undefined}
            className={`block px-3 py-1.5 text-xs hover:bg-muted ${pptxUrl ? "" : "pointer-events-none text-muted-foreground"}`}
            onClick={() => {
              if (pptxUrl) setOpen(false);
            }}
          >
            下载 PPTX
          </a>
          {pdfUrl ? (
            <a
              role="menuitem"
              href={pdfUrl}
              download={pdfName}
              className="block px-3 py-1.5 text-xs hover:bg-muted"
              onClick={() => setOpen(false)}
            >
              下载 PDF
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
