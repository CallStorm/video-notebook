import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Folder, Plus, Search, LayoutGrid, List, Pin, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { NewNotebookDialog } from "@/components/new-notebook-dialog";
import { EditNotebookDialog } from "@/components/edit-notebook-dialog";
import { Brand } from "@/components/brand";
import { UserMenu } from "@/components/user-menu";
import { NotebookCardMenu } from "@/components/notebook-card-menu";
import { CollectionCardMenu } from "@/components/collection-card-menu";
import { CollectionEditDialog } from "@/components/collection-edit-dialog";
import { AddToCollectionDialog } from "@/components/add-to-collection-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Collection {
  id: number;
  name: string;
  icon: string | null;
  notebook_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface Notebook {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
  is_pinned: boolean;
  share_all: boolean;
  source_count: number;
  note_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface NotebookListResponse {
  items: Notebook[];
  total: number;
  page: number;
  size: number;
}

async function fetchNotebooks(
  access: string,
  search: string,
): Promise<NotebookListResponse> {
  return api<NotebookListResponse>(
    `/notebooks?search=${encodeURIComponent(search)}`,
    { access },
  );
}

async function createNotebook(
  access: string,
  body: { title: string; description: string; icon: string | null },
): Promise<Notebook> {
  return api<Notebook>("/notebooks", { method: "POST", body, access });
}

async function deleteNotebook(access: string, id: number): Promise<void> {
  await api(`/notebooks/${id}`, { method: "DELETE", access, raw: true });
}

async function updateNotebook(
  access: string,
  id: number,
  body: { is_pinned?: boolean; title?: string; description?: string | null; icon?: string | null },
): Promise<Notebook> {
  return api<Notebook>(`/notebooks/${id}`, { method: "PATCH", body, access });
}

type View = "grid" | "list";
type Tab = "mine" | "discover" | "collections";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

function initialTab(params: URLSearchParams): Tab {
  const raw = params.get("tab");
  if (raw === "collections" || raw === "discover" || raw === "mine") return raw;
  return "mine";
}

export default function HomePage() {
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = access ?? "";
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [view, setView] = useState<View>("grid");
  const [tab, setTab] = useState<Tab>(() => initialTab(searchParams));
  const [collectionDialog, setCollectionDialog] = useState<
    { mode: "create" | "edit"; id: number | null } | null
  >(null);
  const [addToCollectionId, setAddToCollectionId] = useState<number | null>(null);

  const list = useQuery({
    queryKey: ["notebooks", search],
    queryFn: () => fetchNotebooks(token, search),
    enabled: !!token,
  });

  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: () => api<Collection[]>("/collections", { access: token }),
    enabled: !!token && tab === "collections",
  });

  const patchCollection = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { icon?: string | null; name?: string } }) =>
      api<Collection>(`/collections/${id}`, { method: "PATCH", access: token, body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });

  const removeCollection = useMutation({
    mutationFn: (id: number) => api(`/collections/${id}`, { method: "DELETE", access: token, raw: true }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });

  const create = useMutation({
    mutationFn: (body: { title: string; description: string; icon: string | null }) =>
      createNotebook(token, body),
    onSuccess: (nb) => {
      qc.invalidateQueries({ queryKey: ["notebooks"] });
      setShowNew(false);
      navigate(`/notebooks/${nb.id}`);
    },
  });

  const updateTitle = useMutation({
    mutationFn: ({
      id,
      title,
      description,
      icon,
    }: {
      id: number;
      title: string;
      description: string;
      icon: string | null;
    }) =>
      updateNotebook(token, id, {
        title,
        description: description || null,
        icon,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const togglePin = useMutation({
    mutationFn: ({ id, is_pinned }: { id: number; is_pinned: boolean }) =>
      updateNotebook(token, id, { is_pinned }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteNotebook(token, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const items = list.data?.items ?? [];
  const visible = useMemo(
    () =>
      [...items].sort(
        (a, b) =>
          Number(b.is_pinned) - Number(a.is_pinned) ||
          new Date(b.updated_at ?? 0).getTime() -
            new Date(a.updated_at ?? 0).getTime(),
      ),
    [items],
  );

  const addNotebook =
    addToCollectionId != null
      ? (items.find((n) => n.id === addToCollectionId) ?? null)
      : null;

  // Edit dialog 状态
  const [editing, setEditing] = useState<Notebook | null>(null);

  const errorObj =
    create.error instanceof ApiError
      ? { code: create.error.code, message: create.error.message }
      : null;

  if (!token) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b border-border/60 bg-background/80 backdrop-blur">
          <div className="flex h-16 w-full items-center gap-4 px-6 lg:px-8">
            <Link to="/">
              <Brand />
            </Link>
          </div>
        </header>
        <div className="mx-auto max-w-md p-12 text-center">
          <div className="rounded-3xl border border-border/60 bg-card p-8 shadow-sm">
            <h1 className="mb-2 text-lg font-semibold">登录已过期</h1>
            <p className="mb-4 text-sm text-muted-foreground">
              请重新登录以继续。
            </p>
            <Button
              onClick={() => navigate("/login", { replace: true })}
              className="rounded-full"
            >
              跳到登录页
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* 顶栏：品牌 + tabs + 搜索 + 新建 + 头像 */}
      <header className="sticky top-0 z-20 border-b border-border/40 bg-background/85 backdrop-blur-md">
        <div className="flex h-16 w-full items-center gap-4 px-6 lg:px-8">
          <Link to="/" className="shrink-0">
            <Brand />
          </Link>

          {/* Tabs */}
          <nav className="ml-4 flex items-center gap-1 rounded-full bg-muted/60 p-1">
            <TabButton
              active={tab === "mine"}
              onClick={() => setTab("mine")}
            >
              我的笔记本
            </TabButton>
            <TabButton
              active={tab === "discover"}
              onClick={() => setTab("discover")}
              title="发现（v2）"
            >
              发现
            </TabButton>
            <TabButton active={false} onClick={() => navigate("/search")}>
              聚合搜索
            </TabButton>
            <TabButton active={tab === "collections"} onClick={() => setTab("collections")}>
              集合
            </TabButton>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索笔记本"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 rounded-full border-0 bg-card pl-9 shadow-none"
              />
            </div>

            {/* 视图切换 */}
            <div className="hidden items-center rounded-full bg-card p-0.5 md:flex">
              <Button
                size="icon"
                variant={view === "grid" ? "secondary" : "ghost"}
                className="h-7 w-7 rounded-full shadow-none"
                onClick={() => setView("grid")}
                title="网格"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant={view === "list" ? "secondary" : "ghost"}
                className="h-7 w-7 rounded-full shadow-none"
                onClick={() => setView("list")}
                title="列表"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>

            <UserMenu
              onLogout={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            />
          </div>
        </div>
      </header>

      {/* 内容区 */}
      <div className="w-full px-6 py-8 lg:px-8">
        {tab === "mine" && (
          <MyNotebooksSection
            notebooks={visible}
            isLoading={list.isLoading}
            view={view}
            onCreate={() => setShowNew(true)}
            onEdit={(id) => {
              const nb = items.find((n) => n.id === id);
              if (nb) setEditing(nb);
            }}
            onTogglePin={(id, is_pinned) => togglePin.mutate({ id, is_pinned })}
            onDelete={(id) => {
              if (confirm("删除这个笔记本？")) remove.mutate(id);
            }}
            onAddToCollection={setAddToCollectionId}
          />
        )}
        {tab === "discover" && <PlaceholderSection title="发现" hint="Phase 12 实装 share_all / Discover 视图" />}
        {tab === "collections" && (
          <CollectionsSection
            collections={collections.data ?? []}
            isLoading={collections.isLoading}
            onCreate={() => setCollectionDialog({ mode: "create", id: null })}
            onEdit={(id) => setCollectionDialog({ mode: "edit", id })}
            onDelete={(id) => {
              if (confirm("删除这个集合？")) removeCollection.mutate(id);
            }}
            onRemoveEmoji={(id) => patchCollection.mutate({ id, body: { icon: "" } })}
            onOpen={(id) => navigate(`/collections/${id}`)}
          />
        )}
      </div>

      <NewNotebookDialog
        open={showNew}
        onOpenChange={setShowNew}
        onSubmit={(data) => create.mutate(data)}
        isPending={create.isPending}
        error={errorObj}
      />

      <EditNotebookDialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        notebook={editing}
        onSubmit={(data) => {
          if (!editing) return;
          updateTitle.mutate({ id: editing.id, ...data });
          setEditing(null);
        }}
        isPending={updateTitle.isPending}
        error={
          updateTitle.error instanceof ApiError
            ? { code: updateTitle.error.code, message: updateTitle.error.message }
            : null
        }
      />

      <CollectionEditDialog
        open={collectionDialog !== null}
        mode={collectionDialog?.mode ?? "create"}
        collectionId={collectionDialog?.id ?? null}
        access={token}
        onClose={() => setCollectionDialog(null)}
        onSaved={() => qc.invalidateQueries({ queryKey: ["collections"] })}
      />

      {addNotebook ? (
        <AddToCollectionDialog
          open
          access={token}
          notebookId={addNotebook.id}
          notebookTitle={addNotebook.title}
          notebookIcon={addNotebook.icon}
          onClose={() => setAddToCollectionId(null)}
        />
      ) : null}
    </div>
  );
}

// ── Tab 按钮（仿 NotebookLM 软胶囊） ──────────────────────
function TabButton({
  active,
  onClick,
  disabled,
  title,
  children,
}: {
  active: boolean;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
      className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-background text-foreground shadow-sm"
          : disabled
            ? "cursor-not-allowed text-muted-foreground/40"
            : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

// ── "我的笔记" section ────────────────────────────────────
function MyNotebooksSection({
  notebooks,
  isLoading,
  view,
  onTogglePin,
  onDelete,
  onCreate,
  onEdit,
  onAddToCollection,
}: {
  notebooks: Notebook[];
  isLoading: boolean;
  view: View;
  onTogglePin: (id: number, is_pinned: boolean) => void;
  onDelete: (id: number) => void;
  onEdit: (id: number) => void;
  onCreate: () => void;
  onAddToCollection: (id: number) => void;
}) {
  return (
    <section>
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">我的笔记本</h1>
        <Button onClick={onCreate} className="rounded-full px-4 shadow-none">
          <Plus className="h-4 w-4" />
          <span className="ml-1">新建笔记本</span>
        </Button>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : notebooks.length === 0 ? (
        <div className="flex flex-col items-center justify-center soft-tile px-8 py-20 text-center">
          <p className="mb-1 text-base font-medium text-foreground">还没有笔记本</p>
          <p className="mb-5 max-w-sm text-sm text-muted-foreground">
            创建一本笔记本，上传或粘贴视频链接，开始整理与对话。
          </p>
          <Button onClick={onCreate} className="rounded-full px-5 shadow-none">
            <Plus className="h-4 w-4" />
            <span className="ml-1">新建笔记本</span>
          </Button>
        </div>
      ) : view === "grid" ? (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
          {notebooks.map((nb) => (
            <NotebookCard
              key={nb.id}
              notebook={nb}
              onUpdateTitle={onEdit}
              onTogglePin={() => onTogglePin(nb.id, !nb.is_pinned)}
              onDelete={() => onDelete(nb.id)}
              onAddToCollection={onAddToCollection}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {notebooks.map((nb) => (
            <NotebookRow
              key={nb.id}
              notebook={nb}
              onTogglePin={() => onTogglePin(nb.id, !nb.is_pinned)}
              onDelete={() => onDelete(nb.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function CollectionsSection({
  collections,
  isLoading,
  onCreate,
  onEdit,
  onDelete,
  onRemoveEmoji,
  onOpen,
}: {
  collections: Collection[];
  isLoading: boolean;
  onCreate: () => void;
  onEdit: (id: number) => void;
  onDelete: (id: number) => void;
  onRemoveEmoji: (id: number) => void;
  onOpen: (id: number) => void;
}) {
  return (
    <section>
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">我的集合</h1>
        <Button onClick={onCreate} className="rounded-full px-4 shadow-none">
          <Plus className="h-4 w-4" />
          <span className="ml-1">新建集合</span>
        </Button>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : collections.length === 0 ? (
        <div className="flex flex-col items-center justify-center soft-tile px-8 py-20 text-center">
          <p className="mb-1 text-base font-medium text-foreground">还没有集合</p>
          <p className="mb-5 max-w-sm text-sm text-muted-foreground">
            用集合把相关笔记本归在一起，方便浏览与整理。
          </p>
          <Button onClick={onCreate} className="rounded-full px-5 shadow-none">
            <Plus className="h-4 w-4" />
            <span className="ml-1">新建集合</span>
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
          {collections.map((c) => (
            <div
              key={c.id}
              className="group relative flex min-h-[168px] cursor-pointer flex-col soft-tile soft-tile-hover p-4"
              onClick={() => onOpen(c.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onOpen(c.id);
                }
              }}
              role="link"
              tabIndex={0}
            >
              <div className="flex items-start justify-between gap-2">
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-background/70 text-xl"
                  aria-hidden
                >
                  {c.icon || <Folder className="h-5 w-5 text-foreground/45" />}
                </span>
                <div onClick={(e) => e.stopPropagation()}>
                  <CollectionCardMenu
                    onEdit={() => onEdit(c.id)}
                    onDelete={() => onDelete(c.id)}
                    onRemoveEmoji={() => onRemoveEmoji(c.id)}
                  />
                </div>
              </div>
              <div className="mt-auto pt-8">
                <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight">
                  {c.name}
                </h3>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {c.notebook_count === 1
                    ? "1 本笔记本"
                    : `${c.notebook_count} 本笔记本`}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function PlaceholderSection({ title, hint }: { title: string; hint: string }) {
  return (
    <section>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{title}</h1>
      <div className="soft-tile px-8 py-20 text-center text-sm text-muted-foreground">
        {hint}
      </div>
    </section>
  );
}

// ── Card：NotebookLM 一体浅灰软卡片 ───────────────────────
function NotebookCard({
  notebook: nb,
  onUpdateTitle,
  onTogglePin,
  onDelete,
  onAddToCollection,
}: {
  notebook: Notebook;
  onUpdateTitle: (id: number) => void;
  onTogglePin: (id: number) => void;
  onDelete: (id: number) => void;
  onAddToCollection?: (id: number) => void;
}) {
  return (
    <div className="group relative flex min-h-[168px] flex-col soft-tile soft-tile-hover p-4">
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/notebooks/${nb.id}`}
          className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-background/70 text-xl"
          aria-label={nb.title}
        >
          <span aria-hidden>{nb.icon || "📁"}</span>
          {nb.is_pinned ? (
            <Pin className="absolute -right-1 -top-1 h-3 w-3 fill-amber-500 text-amber-500" />
          ) : null}
        </Link>
        <NotebookCardMenu
          notebookId={nb.id}
          isPinned={nb.is_pinned}
          onRequestEdit={onUpdateTitle}
          onAddToCollection={onAddToCollection}
          onTogglePin={onTogglePin}
          onDelete={onDelete}
        />
      </div>

      <Link to={`/notebooks/${nb.id}`} className="mt-auto flex flex-col pt-8">
        <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight">
          {nb.title}
        </h3>
        <p className="mt-1.5 text-xs text-muted-foreground">
          {formatDate(nb.updated_at)} · {formatSources(nb.source_count)}
        </p>
      </Link>
    </div>
  );
}

// ── Row：列表视图 ────────────────────────────────────────
function NotebookRow({
  notebook: nb,
  onTogglePin,
  onDelete,
}: {
  notebook: Notebook;
  onTogglePin: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 soft-tile soft-tile-hover px-3 py-3">
      <Link
        to={`/notebooks/${nb.id}`}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-background/70 text-xl"
      >
        {nb.icon || "📁"}
      </Link>
      <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold">{nb.title}</div>
        {nb.description && (
          <div className="truncate text-xs text-muted-foreground">
            {nb.description}
          </div>
        )}
      </Link>
      <span className="text-xs text-muted-foreground">
        {formatDate(nb.updated_at)} · {formatSources(nb.source_count)}
      </span>
      <div className="hidden gap-0.5 group-hover:flex">
        <Button
          size="icon"
          variant="ghost"
          onClick={onTogglePin}
          className="h-7 w-7 rounded-full"
        >
          <Pin
            className={`h-3.5 w-3.5 ${nb.is_pinned ? "fill-current text-amber-500" : ""}`}
          />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={onDelete}
          className="h-7 w-7 rounded-full text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
