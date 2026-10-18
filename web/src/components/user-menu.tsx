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
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
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
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onMouseDown={(e) => e.stopPropagation()}
        className="rounded-full transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        title={user?.name ?? "用户"}
      >
        <UserAvatar name={user?.name} />
      </button>

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed inset-0 z-50"
            onMouseDown={() => setOpen(false)}
          >
            <div
              role="menu"
              onClick={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              className="absolute right-4 top-14 w-56 overflow-hidden rounded-lg border bg-popover py-1 text-popover-foreground shadow-lg"
            >
              <div className="border-b px-3 py-2">
                <div className="truncate text-sm font-medium">
                  {user?.name ?? "—"}
                </div>
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
    </div>
  );
}
