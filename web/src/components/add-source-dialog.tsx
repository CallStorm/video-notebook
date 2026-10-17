import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  X,
  Upload as UploadIcon,
  Link2,
  FileVideo,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface AddSourceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Upload chip 选了文件触发 */
  onUploadFiles: (files: File[]) => void;
  /** Websites chip 提交 URL 触发（多行） */
  onSubmitUrls: (urls: string[]) => void;
  uploading?: boolean;
  uploadingMessage?: string;
}

export function AddSourceDialog({
  open,
  onOpenChange,
  onUploadFiles,
  onSubmitUrls,
  uploading,
  uploadingMessage,
}: AddSourceDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [websitesOpen, setWebsitesOpen] = useState(false);
  const [dropped, setDropped] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);

  if (!open) return null;

  return (
    <>
      {createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => onOpenChange(false)}
        >
          <div
            className="w-full max-w-2xl rounded-lg border bg-background shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-center justify-between border-b p-4">
              <div>
                <h2 className="text-base font-semibold">添加来源</h2>
                <p className="text-xs text-muted-foreground">
                  从本机文件或网页链接导入视频
                </p>
              </div>
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

            {/* 拖拽区：拖到此处即触发上传 */}
            <div
              className={`m-4 rounded-lg border-2 border-dashed p-10 text-center text-sm transition-colors ${
                dragOver
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/30"
              }`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const files = Array.from(e.dataTransfer.files);
                setDropped(files);
                if (files.length > 0) {
                  onUploadFiles(files);
                  onOpenChange(false);
                }
              }}
            >
              <div className="mb-3 flex justify-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                  <FileVideo className="h-6 w-6 text-muted-foreground" />
                </div>
              </div>
              <p className="text-muted-foreground">
                拖拽文件到此处，或
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="ml-1 text-blue-600 underline"
                >
                  点击选择
                </button>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                支持 mp4 / mov / webm / mkv（v1 不限大小）
              </p>
              {dropped.length > 0 && (
                <p className="mt-2 text-xs text-emerald-600">
                  已选 {dropped.length} 个文件
                  {uploading ? ` · ${uploadingMessage ?? "上传中…"}` : ""}
                </p>
              )}
              <input
                ref={fileInputRef as React.RefObject<HTMLInputElement>}
                type="file"
                accept="video/mp4,video/webm,video/quicktime,video/x-matroska,.mp4,.webm,.mov,.mkv"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? []);
                  setDropped(files);
                  if (files.length > 0) {
                    onUploadFiles(files);
                    onOpenChange(false);
                  }
                }}
              />
            </div>

            {/* 两个 chip 按钮：Upload files / Websites */}
            <div className="flex flex-wrap items-center gap-2 px-4 pb-4">
              <Chip
                icon={<UploadIcon className="h-4 w-4" />}
                onClick={() => fileInputRef.current?.click()}
              >
                Upload files
              </Chip>
              <Chip
                icon={<Link2 className="h-4 w-4" />}
                onClick={() => setWebsitesOpen(true)}
              >
                Websites
              </Chip>
            </div>

            <footer className="flex items-center justify-end gap-2 border-t p-3 text-xs text-muted-foreground">
              <span>Phase 6 后支持 ASR 自动字幕</span>
            </footer>
          </div>
        </div>,
        document.body,
      )}

      {websitesOpen && (
        <WebsitesDialog
          onClose={() => setWebsitesOpen(false)}
          onSubmit={(urls) => {
            onSubmitUrls(urls);
            setWebsitesOpen(false);
            onOpenChange(false);
          }}
        />
      )}
    </>
  );
}

function Chip({
  icon,
  onClick,
  children,
}: {
  icon: React.ReactNode;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3.5 py-1.5 text-sm font-medium transition-colors hover:bg-muted/40"
    >
      {icon}
      {children}
    </button>
  );
}

function WebsitesDialog({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (urls: string[]) => void;
}) {
  const [text, setText] = useState("");

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex w-full max-w-2xl flex-col rounded-lg border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b p-4">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={onClose}
              className="h-7 w-7"
            >
              <span className="text-base">←</span>
            </Button>
            <h2 className="text-base font-semibold">Website and YouTube URLs</h2>
          </div>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onClose}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="space-y-3 p-4">
          <p className="text-sm text-muted-foreground">
            粘贴 Website 和 YouTube URL，每行一个。
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="https://example.com/video.mp4"
            rows={10}
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li>· 多个 URL 用空格或换行分隔</li>
            <li>· 仅导入页面可见的正文（v2 接 ASR）</li>
            <li>· 仅 YouTube 公开视频可导入</li>
            <li>· 上传失败请检查链接有效性</li>
          </ul>
        </div>

        <footer className="flex items-center justify-end gap-2 border-t p-3">
          <Button
            type="button"
            onClick={() => {
              const urls = text
                .split(/[\s\n]+/)
                .map((s) => s.trim())
                .filter((s) => s.startsWith("http://") || s.startsWith("https://"));
              if (urls.length > 0) onSubmit(urls);
            }}
            disabled={!text.trim()}
            className="rounded-full bg-blue-500 px-6 text-white hover:bg-blue-600 disabled:opacity-50"
          >
            Insert
          </Button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
