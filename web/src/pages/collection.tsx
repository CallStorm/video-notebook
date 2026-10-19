import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, Pin } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Brand } from "@/components/brand";
import { UserMenu } from "@/components/user-menu";
import { NotebookCardMenu } from "@/components/notebook-card-menu";
import { CollectionEditDialog } from "@/components/collection-edit-dialog";
import { AddToCollectionDialog } from "@/components/add-to-collection-dialog";
import { EditNotebookDialog } from "@/components/edit-notebook-dialog";
import { Button } from "@/components/ui/button";

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

interface CollectionDetail {
  id: number;
  name: string;
  icon: string | null;
  notebook_count: number;
  notebooks: Notebook[];
  created_at: string | null;
  updated_at: string | null;
}

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

export default function CollectionPage() {
  const { id } = useParams<{ id: string }>();
  const collectionId = Number(id);
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";
  const qc = useQueryClient();
  const [showEdit, setShowEdit] = useState(false);
  const [editingNb, setEditingNb] = useState<Notebook | null>(null);
  const [addToCollectionId, setAddToCollectionId] = useState<number | null>(null);

  const detail = useQuery({
    queryKey: ["collection", collectionId],
    queryFn: () => api<CollectionDetail>(`/collections/${collectionId}`, { access: token }),
    enabled: !!token && Number.isFinite(collectionId),
  });

  const togglePin = useMutation({
    mutationFn: ({ id: nbId, is_pinned }: { id: number; is_pinned: boolean }) =>
      api<Notebook>(`/notebooks/${nbId}`, {
        method: "PATCH",
        access: token,
        body: { is_pinned },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });

  const removeNb = useMutation({
    mutationFn: (nbId: number) =>
      api(`/notebooks/${nbId}`, { method: "DELETE", access: token, raw: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collection", collectionId] });
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["notebooks"] });
    },
  });

  const updateNb = useMutation({
    mutationFn: ({
      id: nbId,
      title,
      description,
      icon,
    }: {
      id: number;
      title: string;
      description: string;
      icon: string | null;
    }) =>
      api<Notebook>(`/notebooks/${nbId}`, {
        method: "PATCH",
        access: token,
        body: { title, description: description || null, icon },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });

  if (!token) {
    return (
      <div className="mx-auto max-w-md p-12 text-center">
        <p className="mb-4 text-sm text-muted-foreground">请重新登录以继续。</p>
        <Button onClick={() => navigate("/login", { replace: true })} className="rounded-full">
          跳到登录页
        </Button>
      </div>
    );
  }

  if (!Number.isFinite(collectionId)) {
    return (
      <div className="mx-auto max-w-md p-12 text-center text-sm text-muted-foreground">
        无效的集合 ID
      </div>
    );
  }

  const data = detail.data;
  const notebooks = data?.notebooks ?? [];
  const addNotebook =
    addToCollectionId != null
      ? (notebooks.find((n) => n.id === addToCollectionId) ?? null)
      : null;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 border-b bg-background">
        <div className="flex h-16 w-full items-center gap-4 px-6 lg:px-8">
          <Link to="/" className="shrink-0">
            <Brand />
          </Link>
          <div className="ml-auto">
            <UserMenu
              onLogout={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            />
          </div>
        </div>
      </header>

      <div className="w-full p-6 lg:px-8">
        <button
          type="button"
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          onClick={() => navigate("/?tab=collections")}
        >
          <ArrowLeft className="h-4 w-4" />
          My collections
        </button>

        {detail.isLoading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : detail.isError ? (
          <div className="rounded-lg border border-dashed bg-muted/20 p-16 text-center text-sm text-muted-foreground">
            {detail.error instanceof ApiError ? detail.error.message : "加载失败"}
          </div>
        ) : data ? (
          <>
            <header className="mb-6 flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className="text-4xl leading-none">{data.icon || "📂"}</span>
                <div className="min-w-0">
                  <h1 className="truncate text-2xl font-semibold">{data.name}</h1>
                  <p className="text-sm text-muted-foreground">
                    {data.notebook_count === 1
                      ? "1 notebook"
                      : `${data.notebook_count} notebooks`}
                  </p>
                </div>
              </div>
              <Button
                className="rounded-full shadow-none"
                onClick={() => setShowEdit(true)}
              >
                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                Edit
              </Button>
            </header>

            {notebooks.length === 0 ? (
              <div className="soft-tile px-8 py-20 text-center text-sm text-muted-foreground">
                这个集合还没有笔记本。点「Edit」添加。
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
                {notebooks.map((nb) => (
                  <div
                    key={nb.id}
                    className="group relative flex min-h-[168px] flex-col soft-tile soft-tile-hover p-4"
                  >
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
                        onRequestEdit={(nid) => {
                          const found = notebooks.find((n) => n.id === nid);
                          if (found) setEditingNb(found);
                        }}
                        onAddToCollection={setAddToCollectionId}
                        onTogglePin={() =>
                          togglePin.mutate({ id: nb.id, is_pinned: !nb.is_pinned })
                        }
                        onDelete={() => {
                          if (confirm("删除这个笔记本？")) removeNb.mutate(nb.id);
                        }}
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
                ))}
              </div>
            )}
          </>
        ) : null}
      </div>

      <CollectionEditDialog
        open={showEdit}
        mode="edit"
        collectionId={collectionId}
        access={token}
        onClose={() => setShowEdit(false)}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ["collection", collectionId] });
          qc.invalidateQueries({ queryKey: ["collections"] });
        }}
      />

      <EditNotebookDialog
        open={editingNb !== null}
        onOpenChange={(o) => !o && setEditingNb(null)}
        notebook={editingNb}
        onSubmit={(body) => {
          if (!editingNb) return;
          updateNb.mutate({ id: editingNb.id, ...body });
          setEditingNb(null);
        }}
        isPending={updateNb.isPending}
        error={
          updateNb.error instanceof ApiError
            ? { code: updateNb.error.code, message: updateNb.error.message }
            : null
        }
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
