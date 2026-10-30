import React, { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Search, LayoutGrid, List, Pin, Trash2, Clapperboard, MessageSquareText, Sparkles, Settings2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { isRemoteCover } from "@/lib/cover-gen";
import { NewNotebookDialog } from "@/components/new-notebook-dialog";
import { EditNotebookDialog } from "@/components/edit-notebook-dialog";
import { AppHeader } from "@/components/app-header";
import { Brand } from "@/components/brand";
import { UserMenu } from "@/components/user-menu";
import { formatDateZh } from "@/lib/utils";
import { NotebookBookCard } from "@/components/notebook-book-card";
import { GeneratedCover } from "@/components/generated-cover";
import { AutoOrganizeDialog } from "@/components/auto-organize-dialog";
import { ManageTagsDialog } from "@/components/manage-tags-dialog";
import { EditNotebookTagsDialog } from "@/components/edit-notebook-tags-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TagBrief {
  id: number;
  name: string;
  color: string | null;
  notebook_count?: number;
}

interface Notebook {
  id: number;
  title: string;
  description: string | null;
  icon: string | null;
  cover_url?: string | null;
  is_pinned: boolean;
  share_all: boolean;
  source_count: number;
  note_count: number;
  index_status?: string | null;
  indexed_at?: string | null;
  index_error?: string | null;
  tags?: TagBrief[];
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
    `/notebooks?search=${encodeURIComponent(search)}&size=100`,
    { access },
  );
}

async function createNotebook(
  access: string,
  body: { title: string; description: string; cover_url: string },
): Promise<Notebook> {
  return api<Notebook>("/notebooks", { method: "POST", body, access });
}

async function deleteNotebook(access: string, id: number): Promise<void> {
  await api(`/notebooks/${id}`, { method: "DELETE", access, raw: true });
}

async function updateNotebook(
  access: string,
  id: number,
  body: {
    is_pinned?: boolean;
    title?: string;
    description?: string | null;
    icon?: string | null;
    cover_url?: string | null;
  },
): Promise<Notebook> {
  return api<Notebook>(`/notebooks/${id}`, { method: "PATCH", body, access });
}

async function reindexNotebook(access: string, id: number): Promise<void> {
  await api(`/notebooks/${id}/reindex`, { method: "POST", access, body: {} });
}

type View = "grid" | "list";
type Tab = "mine" | "discover";

function formatDate(iso: string | null): string {
  return formatDateZh(iso);
}

function formatSources(n: number): string {
  return n === 1 ? "1 个来源" : `${n} 个来源`;
}

function initialTab(params: URLSearchParams): Tab {
  const raw = params.get("tab");
  if (raw === "discover") return "discover";
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

  React.useEffect(() => {
    const next = initialTab(searchParams);
    if (next === "discover") {
      navigate("/discover", { replace: true });
      return;
    }
    setTab(next);
  }, [searchParams, navigate]);
  const [autoOrganizeOpen, setAutoOrganizeOpen] = useState(false);
  const [manageTagsOpen, setManageTagsOpen] = useState(false);
  const [editTagsNotebookId, setEditTagsNotebookId] = useState<number | null>(null);
  const [selectedTagId, setSelectedTagId] = useState<number | null>(() => {
    const raw = searchParams.get("tag");
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  });

  const list = useQuery({
    queryKey: ["notebooks", search],
    queryFn: () => fetchNotebooks(token, search),
    enabled: !!token,
  });

  const tags = useQuery({
    queryKey: ["tags"],
    queryFn: () => api<TagBrief[]>("/tags", { access: token }),
    enabled: !!token,
  });

  const create = useMutation({
    mutationFn: (body: { title: string; description: string; cover_url: string }) =>
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
      cover_url,
    }: {
      id: number;
      title: string;
      description: string;
      cover_url: string | null;
    }) =>
      updateNotebook(token, id, {
        title,
        description: description || null,
        cover_url,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const togglePin = useMutation({
    mutationFn: ({ id, is_pinned }: { id: number; is_pinned: boolean }) =>
      updateNotebook(token, id, { is_pinned }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const toggleShare = useMutation({
    mutationFn: async ({ id, share_all }: { id: number; share_all: boolean }) => {
      if (share_all) {
        return api<Notebook>(`/notebooks/${id}/share_all`, {
          method: "POST",
          access: token,
        });
      }
      return api<Notebook>(`/notebooks/${id}/share_all`, {
        method: "DELETE",
        access: token,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notebooks"] });
      qc.invalidateQueries({ queryKey: ["notebooks-shared"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteNotebook(token, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const reindex = useMutation({
    mutationFn: (id: number) => reindexNotebook(token, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebooks"] }),
  });

  const items = list.data?.items ?? [];
  const visible = useMemo(() => {
    const sorted = [...items].sort(
      (a, b) =>
        Number(b.is_pinned) - Number(a.is_pinned) ||
        new Date(b.updated_at ?? 0).getTime() -
          new Date(a.updated_at ?? 0).getTime(),
    );
    if (selectedTagId == null) return sorted;
    return sorted.filter((n) => (n.tags ?? []).some((t) => t.id === selectedTagId));
  }, [items, selectedTagId]);

  const editTagsNotebook =
    editTagsNotebookId != null
      ? (items.find((n) => n.id === editTagsNotebookId) ?? null)
      : null;

  const tagRows = tags.data ?? [];

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
          <div className="rounded-2xl border border-border/80 bg-card p-8 shadow-soft">
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
    <div className="page-ambient min-h-screen">
      <AppHeader
        active="mine"
        afterNav={
          tab === "mine" ? (
            <div className="flex justify-end">
              <div className="relative w-full max-w-xs">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="搜索笔记本"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-9 rounded-full border border-border/70 bg-card/90 pl-9 shadow-soft"
                />
              </div>
            </div>
          ) : undefined
        }
        rightSlot={
          <>
            {tab === "mine" ? (
              <div className="hidden items-center rounded-full border border-border/60 bg-card p-0.5 md:flex">
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
            ) : null}
            <UserMenu
              onLogout={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            />
          </>
        }
      />

      {/* 内容区 */}
      <div className="w-full px-6 py-8 lg:px-8">
        {tab === "mine" && (
          <MyNotebooksSection
            notebooks={visible}
            isLoading={list.isLoading}
            view={view}
            tags={tagRows}
            selectedTagId={selectedTagId}
            onSelectTag={setSelectedTagId}
            onManageTags={() => setManageTagsOpen(true)}
            onAutoOrganize={() => setAutoOrganizeOpen(true)}
            onCreate={() => setShowNew(true)}
            onEdit={(id) => {
              const nb = items.find((n) => n.id === id);
              if (nb) setEditing(nb);
            }}
            onTogglePin={(id, is_pinned) => togglePin.mutate({ id, is_pinned })}
            onToggleShare={(id, share_all) => {
              const next = !share_all;
              const ok = confirm(
                next
                  ? "公开后，其他登录用户可在「发现」里看到并打开这本笔记本。确定公开？"
                  : "取消公开后，其他人将无法再从「发现」打开。确定取消？",
              );
              if (ok) toggleShare.mutate({ id, share_all: next });
            }}
            onDelete={(id) => {
              if (confirm("删除这个笔记本？")) remove.mutate(id);
            }}
            onReindex={(id) => {
              if (confirm("重新索引这本笔记本？")) reindex.mutate(id);
            }}
            onEditTags={setEditTagsNotebookId}
          />
        )}
        {tab === "discover" && (
          <DiscoverRedirect />
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


      <AutoOrganizeDialog
        open={autoOrganizeOpen}
        access={token}
        onClose={() => setAutoOrganizeOpen(false)}
        onApplied={() => {
          qc.invalidateQueries({ queryKey: ["tags"] });
          qc.invalidateQueries({ queryKey: ["notebooks"] });
        }}
      />

      <ManageTagsDialog
        open={manageTagsOpen}
        access={token}
        onClose={() => setManageTagsOpen(false)}
      />

      {editTagsNotebook ? (
        <EditNotebookTagsDialog
          open
          access={token}
          notebookId={editTagsNotebook.id}
          notebookTitle={editTagsNotebook.title}
          onClose={() => setEditTagsNotebookId(null)}
        />
      ) : null}
    </div>
  );
}

function MyNotebooksSection({
  notebooks,
  isLoading,
  view,
  tags,
  selectedTagId,
  onSelectTag,
  onManageTags,
  onAutoOrganize,
  onTogglePin,
  onToggleShare,
  onDelete,
  onReindex,
  onCreate,
  onEdit,
  onEditTags,
}: {
  notebooks: Notebook[];
  isLoading: boolean;
  view: View;
  tags: TagBrief[];
  selectedTagId: number | null;
  onSelectTag: (id: number | null) => void;
  onManageTags: () => void;
  onAutoOrganize: () => void;
  onTogglePin: (id: number, is_pinned: boolean) => void;
  onToggleShare: (id: number, share_all: boolean) => void;
  onDelete: (id: number) => void;
  onReindex: (id: number) => void;
  onEdit: (id: number) => void;
  onCreate: () => void;
  onEditTags: (id: number) => void;
}) {
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => onSelectTag(null)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              selectedTagId == null
                ? "bg-primary text-primary-foreground shadow-soft"
                : "bg-muted/80 text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            全部
          </button>
          {tags
            .filter(
              (t) =>
                (t.notebook_count ?? 0) > 0 || selectedTagId === t.id,
            )
            .map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelectTag(t.id)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                selectedTagId === t.id
                  ? "bg-primary text-primary-foreground shadow-soft"
                  : "bg-muted/80 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  backgroundColor:
                    selectedTagId === t.id ? "currentColor" : t.color || "#2F6B4F",
                }}
              />
              {t.name}
              {typeof t.notebook_count === "number" ? (
                <span className="opacity-70">{t.notebook_count}</span>
              ) : null}
            </button>
          ))}
          <button
            type="button"
            onClick={onManageTags}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-border/80 px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-foreground"
          >
            <Settings2 className="h-3 w-3" />
            管理标签
          </button>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onAutoOrganize}
            className="rounded-full px-4"
          >
            <Sparkles className="h-4 w-4" />
            <span className="ml-1">自动整理</span>
          </Button>
          <Button onClick={onCreate} className="rounded-full px-5">
            <Plus className="h-4 w-4" />
            <span className="ml-1">新建笔记本</span>
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : notebooks.length === 0 ? (
        <div className="empty-hero">
          <div className="icon-cluster">
            <span className="bg-primary/10 text-primary">
              <Clapperboard className="h-5 w-5" />
            </span>
            <span className="bg-[hsl(172_50%_94%)] text-[hsl(var(--success))]">
              <MessageSquareText className="h-5 w-5" />
            </span>
            <span className="bg-[hsl(258_80%_96%)] text-[hsl(var(--violet))]">
              <Sparkles className="h-5 w-5" />
            </span>
          </div>
          <p className="mb-1 text-lg font-semibold tracking-tight text-foreground">
            {selectedTagId != null ? "这个标签下还没有笔记本" : "还没有笔记本"}
          </p>
          <p className="mx-auto mb-7 max-w-md text-sm leading-relaxed text-muted-foreground">
            {selectedTagId != null
              ? "换个标签看看，或用「自动整理」重新归类。"
              : "先新建一本，再在笔记本里用「网页搜索」找视频加进来。"}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            {selectedTagId != null ? (
              <Button
                variant="outline"
                onClick={() => onSelectTag(null)}
                className="rounded-full px-5"
              >
                查看全部
              </Button>
            ) : (
              <Button onClick={onCreate} className="rounded-full px-5">
                <Plus className="h-4 w-4" />
                <span className="ml-1">新建笔记本</span>
              </Button>
            )}
          </div>
        </div>
      ) : view === "grid" ? (
        <div className="grid grid-cols-2 gap-x-2.5 gap-y-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8">
          {notebooks.map((nb) => (
            <NotebookBookCard
              key={nb.id}
              notebook={nb}
              onUpdateTitle={onEdit}
              onTogglePin={() => onTogglePin(nb.id, !nb.is_pinned)}
              onToggleShare={() => onToggleShare(nb.id, nb.share_all)}
              onReindex={() => onReindex(nb.id)}
              onDelete={() => onDelete(nb.id)}
              onEditTags={onEditTags}
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


function DiscoverRedirect() {
  const navigate = useNavigate();
  React.useEffect(() => {
    navigate("/discover", { replace: true });
  }, [navigate]);
  return (
    <section>
      <p className="text-sm text-muted-foreground">正在打开发现…</p>
    </section>
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
  const remote = isRemoteCover(nb.cover_url);

  return (
    <div className="group flex items-center gap-3 rounded-2xl border border-border/70 bg-card px-3 py-3 shadow-soft transition-all duration-150 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-accent/40 hover:shadow-soft-md">
      <Link
        to={`/notebooks/${nb.id}`}
        className="relative h-14 w-10 shrink-0 overflow-hidden rounded-md shadow-sm ring-1 ring-black/10"
      >
        {remote ? (
          <img src={nb.cover_url!} alt="" className="h-full w-full object-cover" />
        ) : (
          <GeneratedCover
            title={nb.title}
            coverUrl={nb.cover_url}
            variant={nb.id}
            meta={`${formatDate(nb.updated_at)} · ${formatSources(nb.source_count)}`}
            className="h-full w-full"
          />
        )}
      </Link>
      <Link to={`/notebooks/${nb.id}`} className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 truncate text-sm font-semibold">
          {nb.is_pinned ? <Pin className="h-3 w-3 shrink-0 fill-amber-500 text-amber-500" /> : null}
          {nb.title}
        </div>
        {nb.description ? (
          <div className="truncate text-xs text-muted-foreground">{nb.description}</div>
        ) : null}
      </Link>
      <span className="hidden text-xs text-muted-foreground sm:inline">
        {formatDate(nb.updated_at)} · {formatSources(nb.source_count)}
      </span>
      <div className="hidden gap-0.5 group-hover:flex">
        <Button size="icon" variant="ghost" onClick={onTogglePin} className="h-7 w-7 rounded-full">
          <Pin className={`h-3.5 w-3.5 ${nb.is_pinned ? "fill-current text-amber-500" : ""}`} />
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
