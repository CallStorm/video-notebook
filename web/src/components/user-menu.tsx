import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { LogOut, Moon, Settings, Sun } from "lucide-react";
import { UserAvatar } from "@/components/user-avatar";
import { useAuth } from "@/lib/auth";
import { SKINS } from "@/lib/skin";
import { useAppearance } from "@/lib/use-appearance";

interface UserMenuProps {
  /** 点菜单里「退出登录」后调用。 */
  onLogout: () => void;
}

export function UserMenu({ onLogout }: UserMenuProps) {
  const { user } = useAuth();
  const { skin, dark, setSkin, setDark } = useAppearance();
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
      const menuWidth = 260;
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
              className="absolute w-[260px] overflow-hidden rounded-xl border border-border/80 bg-popover text-popover-foreground shadow-lg"
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

              <div className="border-b border-border/70 px-3 py-2.5">
                <div className="mb-2 text-[11px] font-medium tracking-wide text-muted-foreground">
                  外观 · 皮肤
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {SKINS.map((item) => {
                    const active = skin === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        role="menuitemradio"
                        aria-checked={active}
                        title={item.hint}
                        onClick={() => setSkin(item.id)}
                        className={
                          "flex items-center gap-2 rounded-lg border px-2 py-1.5 text-left transition " +
                          (active
                            ? "border-primary/40 bg-primary/10 text-foreground shadow-soft"
                            : "border-border/60 bg-card/60 text-muted-foreground hover:border-primary/25 hover:bg-accent hover:text-foreground")
                        }
                      >
                        <span className="flex shrink-0 items-center -space-x-1" aria-hidden>
                          {item.swatches.map((c) => (
                            <span
                              key={c}
                              className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10"
                              style={{ backgroundColor: c }}
                            />
                          ))}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-xs font-medium leading-tight">
                            {item.label}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-2 flex items-center gap-1 rounded-lg border border-border/60 bg-muted/30 p-0.5">
                  <button
                    type="button"
                    onClick={() => setDark(false)}
                    className={
                      "flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition " +
                      (!dark
                        ? "bg-card text-foreground shadow-soft"
                        : "text-muted-foreground hover:text-foreground")
                    }
                  >
                    <Sun className="h-3.5 w-3.5" />
                    浅色
                  </button>
                  <button
                    type="button"
                    onClick={() => setDark(true)}
                    className={
                      "flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition " +
                      (dark
                        ? "bg-card text-foreground shadow-soft"
                        : "text-muted-foreground hover:text-foreground")
                    }
                  >
                    <Moon className="h-3.5 w-3.5" />
                    深色
                  </button>
                </div>
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
