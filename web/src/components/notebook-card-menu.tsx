import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Pencil,
  FolderPlus,
  Pin,
  PinOff,
  Trash2,
  MoreVertical,
  Bell,
} from "lucide-react";

interface NotebookCardMenuProps {
  notebookId: number;
  isPinned: boolean;
  hasNotification?: boolean;
  /** 触发「Edit Notebook」全屏弹窗。父级在收到回调时打开 dialog。 */
  onRequestEdit: (id: number) => void;
  onTogglePin: (id: number) => void;
  onDelete: (id: number) => void;
}

interface Anchor {
  top: number; // 视口坐标
  left: number;
  // 面板首选放在按钮右下；放不下就放左下
  align: "right" | "left";
}

const MENU_W = 192; // w-48
const MENU_H = 220; // 大致高度，留缓冲
const GAP = 6; // 按钮与菜单间距

export function NotebookCardMenu({
  notebookId,
  isPinned,
  hasNotification,
  onRequestEdit,
  onTogglePin,
  onDelete,
}: NotebookCardMenuProps) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // 点 ⋮ 时算锚点
  const onTrigger = () => {
    if (triggerRef.current) {
      const r = triggerRef.current.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      // 优先放在按钮正下方 / 右下方（菜单与按钮左对齐）。如果右边顶出，按钮左对齐改用右对齐。
      const leftIfRightAlign = r.right;
      const leftIfLeftAlign = r.left - MENU_W;
      const wouldOverflowRight = leftIfRightAlign + MENU_W > vw - 4;
      const wouldOverflowLeft = leftIfLeftAlign < 4;
      const align: Anchor["align"] = wouldOverflowRight && !wouldOverflowLeft
        ? "left"
        : "right";
      // top：先在按钮下方；放不下就向上
      let top = r.bottom + GAP;
      if (top + MENU_H > vh - 4) {
        top = Math.max(4, r.top - MENU_H - GAP);
      }
      const left = align === "right" ? leftIfRightAlign : leftIfLeftAlign;
      setAnchor({ top, left, align });
    }
    setOpen(true);
  };

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // 滚动/缩放时关掉（锚点会失效）
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
      <div className="absolute right-2 top-2 flex items-center gap-0.5">
        {/* 通知铃：v1 仅装饰 */}
        <button
          type="button"
          className="rounded-full p-1 text-muted-foreground/60 transition-colors hover:bg-foreground/5 hover:text-muted-foreground"
          title={hasNotification ? "有新动态" : "无新动态"}
        >
          <Bell className="h-3.5 w-3.5" />
        </button>

        {/* 三点菜单触发器 */}
        <button
          ref={triggerRef}
          type="button"
          onClick={onTrigger}
          className="rounded-full p-1 text-muted-foreground/60 transition-colors hover:bg-foreground/5 hover:text-foreground"
          title="更多"
        >
          <MoreVertical className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 锚点小菜单：portal 到 body 根，position: fixed 在按钮附近 */}
      {open && anchor && typeof document !== "undefined"
        ? createPortal(
            <div
              className="fixed inset-0 z-50"
              onClick={() => setOpen(false)}
            >
              <div
                role="menu"
                onClick={(e) => e.stopPropagation()}
                className="absolute w-48 overflow-hidden rounded-lg border bg-popover py-1 text-popover-foreground shadow-lg"
                style={{
                  top: anchor.top,
                  left: anchor.align === "right" ? anchor.left : anchor.left,
                }}
              >
                {(
                  <>
                    <Item
                      icon={<Pencil className="h-3.5 w-3.5" />}
                      onClick={() => {
                        setOpen(false);
                        onRequestEdit(notebookId);
                      }}
                    >
                      Edit title
                    </Item>
                    <Item
                      icon={<FolderPlus className="h-3.5 w-3.5" />}
                      disabled
                      hint="Phase 12"
                    >
                      Add to collection
                    </Item>
                    <Item
                      icon={
                        isPinned ? (
                          <PinOff className="h-3.5 w-3.5" />
                        ) : (
                          <Pin className="h-3.5 w-3.5" />
                        )
                      }
                      onClick={() => {
                        onTogglePin(notebookId);
                        setOpen(false);
                      }}
                    >
                      {isPinned ? "Unpin" : "Pin"}
                    </Item>
                    <div className="my-1 h-px bg-border" />
                    <Item
                      icon={<Trash2 className="h-3.5 w-3.5" />}
                      danger
                      onClick={() => {
                        onDelete(notebookId);
                        setOpen(false);
                      }}
                    >
                      Delete
                    </Item>
                  </>
                )}
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function Item({
  icon,
  onClick,
  disabled,
  danger,
  hint,
  children,
}: {
  icon: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  const color = danger
    ? "text-destructive hover:bg-destructive/10"
    : "text-foreground hover:bg-foreground/5";
  const cls = disabled
    ? "text-muted-foreground/50 cursor-not-allowed"
    : `${color} cursor-pointer`;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs ${cls}`}
    >
      {icon}
      <span className="flex-1">{children}</span>
      {hint && <span className="text-[10px] text-muted-foreground/60">{hint}</span>}
    </button>
  );
}
