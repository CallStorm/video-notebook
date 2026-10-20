import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { LogOut, Settings } from "lucide-react";
import { UserAvatar } from "@/components/user-avatar";
import { useAuth } from "@/lib/auth";

interface UserMenuProps {
  /** 点菜单里「退出登录」后调用。 */
  onLogout: () => void;
}

export function UserMenu({ onLogout }: UserMenuProps) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
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

  function toggleMenu() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      const menuWidth = 224;
      const left = Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8));
      setAnchor({ top: rect.bottom + 8, left });
    }
    setOpen((v) => !v);
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={toggleMenu}
        onMouseDown={(e) => e.stopPropagation()}
        className="rounded-full transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={user?.name ?? "用户"}
      >
        <UserAvatar name={user?.name} />
      </button>

      {open &&
        anchor &&
        typeof document !== "undefined" &&
        createPortal(
          <div className="fixed inset-0 z-[200]" onMouseDown={() => setOpen(false)}>
            <div
              role="menu"
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              className="absolute w-56 overflow-hidden rounded-xl border border-border/80 bg-popover text-popover-foreground shadow-lg"
              style={{ top: anchor.top, left: anchor.left }}
            >
              <div className="border-b border-border/70 px-3 py-2">
                <div className="truncate text-sm font-medium">{user?.name ?? "—"}</div>
                {user && (
                  <div className="truncate text-xs text-muted-foreground">
                    {user.role === "admin" ? "管理员" : "用户"} · {user.phone}
                  </div>
                )}
              </div>
              {user?.role === "admin" && (
                <Link
                  to="/admin"
                  role="menuitem"
                  onClick={() => setOpen(false)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                >
                  <Settings className="h-4 w-4" />
                  后台
                </Link>
              )}
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onLogout();
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-destructive hover:bg-destructive/10"
              >
                <LogOut className="h-4 w-4" />
                退出登录
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
