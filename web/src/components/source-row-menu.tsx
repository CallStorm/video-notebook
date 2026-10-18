import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { MoreVertical, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SourceRowMenu({
  onRename,
  onRemove,
  onRegenerate,
  onRetryFetch,
}: {
  onRename: () => void;
  onRemove: () => void;
  onRegenerate?: () => void;
  onRetryFetch?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        title="更多"
        className={`rounded-full p-1 text-muted-foreground hover:bg-foreground/5 hover:text-foreground ${
          open ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
        onClick={(event) => {
          event.stopPropagation();
          const rect = triggerRef.current?.getBoundingClientRect();
          if (rect) {
            const menuWidth = 168;
            const left = Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8));
            setAnchor({ top: rect.bottom + 6, left });
          }
          setOpen(true);
        }}
      >
        <MoreVertical className="h-3.5 w-3.5" />
      </button>
      {open && anchor
        ? createPortal(
            <div className="fixed inset-0 z-50" onClick={() => setOpen(false)}>
              <div
                role="menu"
                className="absolute w-[168px] overflow-hidden rounded-xl border bg-popover py-1 text-popover-foreground shadow-lg"
                style={{ top: anchor.top, left: anchor.left }}
                onClick={(event) => event.stopPropagation()}
              >
                <MenuItem
                  icon={<Trash2 className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setOpen(false);
                    onRemove();
                  }}
                >
                  删除
                </MenuItem>
                <MenuItem
                  icon={<Pencil className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setOpen(false);
                    onRename();
                  }}
                >
                  重命名
                </MenuItem>
                {onRetryFetch ? (
                  <MenuItem
                    icon={<RefreshCw className="h-3.5 w-3.5" />}
                    onClick={() => {
                      setOpen(false);
                      onRetryFetch();
                    }}
                  >
                    重新抓取
                  </MenuItem>
                ) : null}
                {onRegenerate ? (
                  <MenuItem
                    icon={<RefreshCw className="h-3.5 w-3.5" />}
                    onClick={() => {
                      setOpen(false);
                      onRegenerate();
                    }}
                  >
                    重新生成
                  </MenuItem>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function MenuItem({
  icon,
  onClick,
  children,
}: {
  icon: ReactNode;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted"
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  );
}

export function SourceRenameDialog({
  open,
  title,
  pending,
  error,
  heading = "重命名来源",
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  pending?: boolean;
  error?: string | null;
  heading?: string;
  onClose: () => void;
  onSubmit: (title: string) => void;
}) {
  const [value, setValue] = useState(title);

  useEffect(() => {
    if (open) setValue(title);
  }, [open, title]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <form
        className="w-full max-w-md rounded-lg border bg-background p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          const next = value.trim();
          if (!next) return;
          onSubmit(next);
        }}
      >
        <h2 className="mb-3 text-base font-semibold">{heading}</h2>
        <Input value={value} onChange={(event) => setValue(event.target.value)} autoFocus maxLength={255} />
        {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button type="submit" disabled={pending || !value.trim()}>
            保存
          </Button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
