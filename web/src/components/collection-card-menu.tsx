import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreVertical, Pencil, Sparkles, Trash2 } from "lucide-react";

const MENU_W = 192;
const MENU_H = 160;
const GAP = 6;

export function CollectionCardMenu({
  onEdit,
  onDelete,
  onGenerateCover,
  generatingCover,
}: {
  onEdit: () => void;
  onDelete: () => void;
  onGenerateCover?: () => void;
  generatingCover?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const onTrigger = () => {
    if (triggerRef.current) {
      const r = triggerRef.current.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      let left = r.right - MENU_W;
      if (left < 4) left = r.left;
      if (left + MENU_W > vw - 4) left = Math.max(4, vw - MENU_W - 4);
      let top = r.bottom + GAP;
      if (top + MENU_H > vh - 4) top = Math.max(4, r.top - MENU_H - GAP);
      setAnchor({ top, left });
    }
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onTrigger();
        }}
        className="rounded-full bg-white/90 p-1.5 text-muted-foreground/70 shadow-sm ring-1 ring-black/5 backdrop-blur-sm transition-colors hover:bg-white hover:text-foreground"
        title="更多"
      >
        <MoreVertical className="h-3.5 w-3.5" />
      </button>
      {open && anchor && typeof document !== "undefined"
        ? createPortal(
            <div className="fixed inset-0 z-[200]" onClick={() => setOpen(false)}>
              <div
                role="menu"
                onClick={(e) => e.stopPropagation()}
                className="absolute w-48 overflow-hidden rounded-xl border border-border/80 bg-popover py-1 text-popover-foreground shadow-lg"
                style={{ top: anchor.top, left: anchor.left }}
              >
                <MenuItem
                  icon={<Pencil className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setOpen(false);
                    onEdit();
                  }}
                >
                  编辑
                </MenuItem>
                {onGenerateCover ? (
                  <MenuItem
                    icon={<Sparkles className="h-3.5 w-3.5" />}
                    onClick={() => {
                      setOpen(false);
                      onGenerateCover();
                    }}
                  >
                    {generatingCover ? "生成封面中…" : "生成封面"}
                  </MenuItem>
                ) : null}
                <MenuItem
                  icon={<Trash2 className="h-3.5 w-3.5" />}
                  danger
                  onClick={() => {
                    setOpen(false);
                    onDelete();
                  }}
                >
                  删除
                </MenuItem>
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
  danger,
  children,
}: {
  icon: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  const color = danger
    ? "text-destructive hover:bg-destructive/10"
    : "text-foreground hover:bg-foreground/5";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs ${color}`}
    >
      {icon}
      <span className="flex-1">{children}</span>
    </button>
  );
}
