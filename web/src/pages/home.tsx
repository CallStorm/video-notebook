import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Folder, Plus, Search, LayoutGrid, List, Pin, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { HealthGate } from "@/components/health-gate";
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
type Tab = "all" | "mine" | "discover" | "collections";

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
  return n === 1 ? "1 source" : `${n} sources`;
}

function initialTab(params: URLSearchParams): Tab {
  const raw = params.get("tab");
  if (raw === "collections" || raw === "discover" || raw === "mine" || raw === "all") return raw;
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
        <header className="border-b">
          <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-6">
            <Link to="/">
              <Brand />
            </Link>
          </div>
        </header>
        <div className="mx-auto max-w-md p-12 text-center">
          <div className="rounded-lg border bg-card p-8">
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
      <header className="sticky top-0 z-20 border-b bg-background">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-6">
          <Link to="/" className="shrink-0">
            <Brand />
          </Link>

          {/* Tabs */}
          <nav className="ml-4 flex items-center gap-1">
            <TabButton
              active={tab === "all"}
              disabled
              title="All（v2）"
            >
              All
            </TabButton>
            <TabButton
              active={tab === "mine"}
              onClick={() => setTab("mine")}
            >
              我的笔记
            </TabButton>
            <TabButton
              active={tab === "discover"}
              onClick={() => setTab("discover")}
              title="发现（v2）"
            >
              发现
            </TabButton>
            <TabButton active={tab === "collections"} onClick={() => setTab("collections")}>
              集合
            </TabButton>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search notebooks"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rounded-full pl-9"
              />
            </div>

            {/* 视图切换 */}
            <div className="hidden items-center rounded-full border p-0.5 md:flex">
              <Button
                size="icon"
                variant={view === "grid" ? "secondary" : "ghost"}
                className="h-7 w-7 rounded-full"
                onClick={() => setView("grid")}
                title="网格"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant={view === "list" ? "secondary" : "ghost"}
                className="h-7 w-7 rounded-full"
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
      <div className="mx-auto max-w-6xl p-6">
        {(tab === "all" || tab === "mine") && (
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

      <details className="mx-auto mb-6 max-w-6xl rounded-md border bg-muted/20 p-3 text-xs text-muted-foreground">
        <summary className="mx-auto max-w-6xl cursor-pointer">API 健康检查（开发用）</summary>
        <div className="mx-auto mt-2 max-w-6xl">
          <HealthGate />
        </div>
      </details>

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

// ── Tab 按钮（仿 Gemini） ─────────────────────────────────
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
      className={`relative rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-blue-50 text-foreground"
          : disabled
            ? "text-muted-foreground/50"
            : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      }`}
    >
      {children}
      {active && (
        <span className="absolute -bottom-px left-1/2 h-0.5 w-6 -translate-x-1/2 rounded-full bg-foreground/60" />
      )}
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
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">My notebooks</h1>
        <Button
          onClick={onCreate}
          className="rounded-full bg-blue-500 px-4 text-white hover:bg-blue-600"
        >
          <Plus className="h-4 w-4" />
          <span className="ml-1">New notebook</span>
        </Button>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : notebooks.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/20 p-16 text-center text-sm text-muted-foreground">
          还没有笔记本。点「New notebook」开始。
        </div>
      ) : view === "grid" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
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
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">My collections</h1>
        <Button
          onClick={onCreate}
          className="rounded-full bg-blue-500 px-4 text-white hover:bg-blue-600"
        >
          <Plus className="h-4 w-4" />
          <span className="ml-1">New collection</span>
        </Button>
      </header>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : collections.length === 0 ? (
        <div className="rounded-lg border border-dashed bg-muted/20 p-16 text-center text-sm text-muted-foreground">
          还没有集合。点「New collection」开始。
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {collections.map((c) => (
            <div
              key={c.id}
              className="group relative flex cursor-pointer flex-col overflow-hidden rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:shadow-md"
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
              <header className="mb-3 flex items-start justify-between">
                <span className="text-3xl leading-none" aria-hidden>
                  {c.icon || <Folder className="h-8 w-8 text-muted-foreground" />}
                </span>
                <div onClick={(e) => e.stopPropagation()}>
                  <CollectionCardMenu
                    onEdit={() => onEdit(c.id)}
                    onDelete={() => onDelete(c.id)}
                    onRemoveEmoji={() => onRemoveEmoji(c.id)}
                  />
                </div>
              </header>
              <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{c.name}</h3>
              <div className="mt-auto pt-3 text-xs text-muted-foreground">
                {c.notebook_count === 1 ? "1 notebook" : `${c.notebook_count} notebooks`}
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
      <h1 className="mb-4 text-2xl font-semibold">{title}</h1>
      <div className="rounded-lg border border-dashed bg-muted/20 p-16 text-center text-sm text-muted-foreground">
        {hint}
      </div>
    </section>
  );
}

// ── Card：仿 Gemini Notebook ──────────────────────────────
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
    <div className="group relative flex flex-col overflow-hidden rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:shadow-md">
      {/* 头部：emoji 左 + 右上角 bell + 三点菜单 */}
      <header className="mb-3 flex items-start justify-between">
        <Link
          to={`/notebooks/${nb.id}`}
          className="text-3xl leading-none"
          aria-label={nb.title}
        >
          {nb.icon || "📁"}
        </Link>
        <NotebookCardMenu
          notebookId={nb.id}
          isPinned={nb.is_pinned}
          onRequestEdit={onUpdateTitle}
          onAddToCollection={onAddToCollection}
          onTogglePin={onTogglePin}
          onDelete={onDelete}
        />
      </header>

      {/* 标题 + 描述 */}
      <Link to={`/notebooks/${nb.id}`} className="block space-y-1">
        <h3 className="line-clamp-2 text-sm font-semibold leading-snug">
          {nb.title}
        </h3>
        {nb.description && (
          <p className="line-clamp-1 text-xs text-muted-foreground">
            {nb.description}
          </p>
        )}
      </Link>

      {/* 底部：日期 · 来源数 */}
      <div className="mt-auto pt-3 text-xs text-muted-foreground">
        <p>
          {formatDate(nb.updated_at)} · {formatSources(nb.source_count)}
        </p>
      </div>
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
    <div className="group flex items-center gap-3 rounded-lg border bg-card p-3 hover:shadow-sm">
      <Link to={`/notebooks/${nb.id}`} className="text-2xl">
        {nb.icon || "📁"}
      </Link>
      <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{nb.title}</div>
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
          className="h-7 w-7"
        >
          <Pin
            className={`h-3.5 w-3.5 ${nb.is_pinned ? "fill-current text-amber-500" : ""}`}
          />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={onDelete}
          className="h-7 w-7 text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
