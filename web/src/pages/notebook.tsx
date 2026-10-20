import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Plus,
  Upload as UploadIcon,
  Link2,
  Loader2,
  Library,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { usePersistedBool } from "@/lib/use-persisted-bool";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AddSourceDialog } from "@/components/add-source-dialog";
import { SourceTranscript } from "@/components/source-transcript";
import { SourceRenameDialog, SourceRowMenu } from "@/components/source-row-menu";
import { NotebookChat, readChatStream, type ChatCitation, type ChatMessage, type ChatRelay } from "@/components/notebook-chat";
import { MarkdownMessage } from "@/components/chat-markdown";
import { StudioCollapsedRail, StudioPanel } from "@/components/studio-panel";
import { StudioMindmap } from "@/components/studio-mindmap";
import { StudioSlides } from "@/components/studio-slides";
import { StudioFile } from "@/components/studio-file";
import { UserMenu } from "@/components/user-menu";
import { Copy, StickyNote, X } from "lucide-react";

interface VideoRead {
  id: number;
  source_type: "upload" | "url";
  source_url: string | null;
  storage_key: string | null;
  mime: string | null;
  duration_ms: number | null;
  width: number | null;
  height: number | null;
  size_bytes: number | null;
  content_hash: string | null;
  status: "pending" | "probing" | "ready" | "failed";
  error_message: string | null;
  subtitle_status: "pending" | "processing" | "ready" | "failed";
  subtitle_error: string | null;
  overview_status: "pending" | "processing" | "ready" | "failed";
  overview_text: string | null;
  overview_error: string | null;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface SourceSummary {
  notebook_id: number;
  video_id: number;
  sort: number;
  selected_for_chat: boolean;
  video: VideoRead;
}

interface NoteRead {
  id: number;
  title: string;
  content_text: string;
  message_id: number | null;
  citations: ChatCitation[];
  selected_for_chat: boolean;
  created_at: string | null;
}

interface NotebookDetail {
  id: number;
  title: string;
  icon: string | null;
  is_pinned: boolean;
  share_all: boolean;
  source_count: number;
  note_count: number;
  sources: SourceSummary[];
  notes?: NoteRead[];
}

async function fetchNotebook(access: string, id: number): Promise<NotebookDetail> {
  return api<NotebookDetail>(`/notebooks/${id}`, { access });
}

async function uploadSource(
  access: string,
  notebookId: number,
  file: File,
): Promise<VideoRead> {
  const form = new FormData();
  form.append("file", file);
  return api<VideoRead>(`/notebooks/${notebookId}/sources/upload`, {
    method: "POST",
    body: form,
    access,
  });
}

async function fetchSourceUrl(
  access: string,
  notebookId: number,
  url: string,
): Promise<VideoRead> {
  return api<VideoRead>(`/notebooks/${notebookId}/sources/fetch`, {
    method: "POST",
    body: { url },
    access,
  });
}

async function deleteSource(access: string, videoId: number): Promise<void> {
  await api(`/sources/${videoId}`, { method: "DELETE", access, raw: true });
}

async function renameSource(access: string, videoId: number, title: string): Promise<VideoRead> {
  return api<VideoRead>(`/sources/${videoId}`, { method: "PATCH", access, body: { title } });
}

async function regenerateSource(access: string, videoId: number): Promise<void> {
  await api(`/sources/${videoId}/subtitle/regenerate`, { method: "POST", access });
}

async function retryFetchSource(access: string, videoId: number): Promise<VideoRead> {
  return api<VideoRead>(`/sources/${videoId}/retry-fetch`, { method: "POST", access });
}

async function cancelFetchSource(access: string, videoId: number): Promise<VideoRead> {
  return api<VideoRead>(`/sources/${videoId}/cancel-fetch`, { method: "POST", access });
}

function fmtDuration(ms: number | null): string {
  if (!ms) return "—";
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtSize(b: number | null): string {
  if (!b) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}


const LEFT_COLLAPSE_KEY = "vn.notebook.panel.leftCollapsed";
const RIGHT_COLLAPSE_KEY = "vn.notebook.panel.rightCollapsed";

function SideRail({
  side,
  label,
  icon: Icon,
  badge,
  onExpand,
}: {
  side: "left" | "right";
  label: string;
  icon: typeof Library;
  badge?: string | number | null;
  onExpand: () => void;
}) {
  const ExpandIcon = side === "left" ? PanelLeftOpen : PanelRightOpen;
  return (
    <div className="panel-rail">
      <Button
        size="icon"
        variant="ghost"
        className="h-8 w-8 rounded-full hover:bg-primary/10 hover:text-primary"
        title={`展开${label}`}
        aria-label={`展开${label}`}
        onClick={onExpand}
      >
        <ExpandIcon className="h-4 w-4" />
      </Button>
      <button
        type="button"
        className="flex flex-1 flex-col items-center gap-3 rounded-xl px-0.5 py-2 text-muted-foreground transition-colors hover:bg-card hover:text-foreground hover:shadow-soft"
        title={`展开${label}`}
        onClick={onExpand}
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-soft">
          <Icon className="h-4 w-4" />
        </span>
        <span className="panel-rail-label">{label}</span>
        {badge != null && badge !== "" ? (
          <span className="panel-count">{badge}</span>
        ) : null}
      </button>
    </div>
  );
}

export default function NotebookPage() {
  const { id } = useParams<{ id: string }>();
  const notebookId = Number(id);
  const { access, logout } = useAuth();
  const navigate = useNavigate();
  const token = access ?? "";
  const qc = useQueryClient();
  // fileInputRef removed: upload now lives inside AddSourceDialog
  const [previewTaskId, setPreviewTaskId] = useState<number | null>(null);
  const [previewFormat, setPreviewFormat] = useState<string | null>(null);
  const [previewExpanded, setPreviewExpanded] = useState(false);
  const [relay, setRelay] = useState<ChatRelay | null>(null);
  const discussing = useRef(false);

  const detail = useQuery({
    queryKey: ["notebook", notebookId],
    queryFn: () => fetchNotebook(token, notebookId),
    enabled: !!token && !!notebookId,
    refetchInterval: (query) => {
      const sources = query.state.data?.sources ?? [];
      const busy = sources.some((source) => {
        const video = source.video;
        return (
          video.status === "pending" ||
          video.status === "probing" ||
          video.subtitle_status === "pending" ||
          video.subtitle_status === "processing" ||
          video.overview_status === "processing"
        );
      });
      return busy ? 2000 : false;
    },
  });

  const preview = useQuery({
    queryKey: ["studio-task", notebookId, previewTaskId],
    queryFn: () => api<StudioTaskDetail>(`/studio/tasks/${previewTaskId}`, { access: token }),
    enabled: !!token && previewTaskId != null,
  });

  useEffect(() => {
    setPreviewTaskId(null);
    setPreviewFormat(null);
    setPreviewExpanded(false);
    setPendingCapabilityId(null);
    setRelay(null);
    discussing.current = false;
  }, [notebookId]);

  const [showAddSource, setShowAddSource] = useState(false);
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);
  const [focusCue, setFocusCue] = useState<{ videoId: number; lineNo: number } | null>(null);
  const [openNoteId, setOpenNoteId] = useState<number | null>(null);
  const [renameTarget, setRenameTarget] = useState<
    { kind: "source"; id: number; title: string } | { kind: "note"; id: number; title: string } | null
  >(null);
  const [leftCollapsed, setLeftCollapsed] = usePersistedBool(LEFT_COLLAPSE_KEY, false);
  const [rightCollapsed, setRightCollapsed] = usePersistedBool(RIGHT_COLLAPSE_KEY, false);
  const [pendingCapabilityId, setPendingCapabilityId] = useState<number | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => uploadSource(token, notebookId, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const fetchUrl = useMutation({
    mutationFn: (url: string) => fetchSourceUrl(token, notebookId, url),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const removeSource = useMutation({
    mutationFn: (videoId: number) => deleteSource(token, videoId),
    onSuccess: (_data, videoId) => {
      if (selectedVideoId === videoId) setSelectedVideoId(null);
      qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
    },
  });

  const rename = useMutation({
    mutationFn: ({ videoId, title }: { videoId: number; title: string }) =>
      renameSource(token, videoId, title),
    onSuccess: () => {
      setRenameTarget(null);
      qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
    },
  });

  const renameNote = useMutation({
    mutationFn: ({ noteId, title }: { noteId: number; title: string }) =>
      api<NoteRead>(`/notes/${noteId}`, { method: "PATCH", access: token, body: { title } }),
    onSuccess: () => {
      setRenameTarget(null);
      qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
    },
  });

  const removeNote = useMutation({
    mutationFn: (noteId: number) => api(`/notes/${noteId}`, { method: "DELETE", access: token, raw: true }),
    onSuccess: (_data, noteId) => {
      if (openNoteId === noteId) setOpenNoteId(null);
      qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
      qc.invalidateQueries({ queryKey: ["chat", notebookId] });
    },
  });

  const regenerate = useMutation({
    mutationFn: (videoId: number) => regenerateSource(token, videoId),
    onSuccess: (_data, videoId) => {
      qc.invalidateQueries({ queryKey: ["notebook", notebookId] });
      qc.invalidateQueries({ queryKey: ["subtitle", videoId] });
    },
  });

  const retryFetch = useMutation({
    mutationFn: (videoId: number) => retryFetchSource(token, videoId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const cancelFetch = useMutation({
    mutationFn: (videoId: number) => cancelFetchSource(token, videoId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const setSelection = useMutation({
    mutationFn: (input: { videoId?: number; selected: boolean }) =>
      input.videoId == null
        ? api(`/notebooks/${notebookId}/sources/selection`, {
            method: "PATCH",
            access: token,
            body: { selected_for_chat: input.selected },
          })
        : api(`/notebooks/${notebookId}/sources/${input.videoId}`, {
            method: "PATCH",
            access: token,
            body: { selected_for_chat: input.selected },
          }),
    onMutate: (input) => {
      qc.setQueryData<NotebookDetail>(["notebook", notebookId], (current) => {
        if (!current) return current;
        return {
          ...current,
          sources: current.sources.map((source) =>
            input.videoId == null || source.video_id === input.videoId
              ? { ...source, selected_for_chat: input.selected }
              : source,
          ),
        };
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  const setNoteSelection = useMutation({
    mutationFn: (input: { noteId: number; selected: boolean }) =>
      api(`/notebooks/${notebookId}/notes/${input.noteId}`, {
        method: "PATCH",
        access: token,
        body: { selected_for_chat: input.selected },
      }),
    onMutate: (input) => {
      qc.setQueryData<NotebookDetail>(["notebook", notebookId], (current) => {
        if (!current) return current;
        return {
          ...current,
          notes: (current.notes ?? []).map((note) =>
            note.id === input.noteId ? { ...note, selected_for_chat: input.selected } : note,
          ),
        };
      });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["notebook", notebookId] }),
  });

  if (!token) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Card>
          <CardHeader>
            <CardTitle>请先登录</CardTitle>
          </CardHeader>
          <CardContent>
            <a href="/login" className="text-blue-600 underline">
              跳到登录页
            </a>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (detail.isLoading) {
    return <p className="p-6 text-sm text-muted-foreground">加载中…</p>;
  }
  if (detail.error instanceof ApiError && detail.error.status === 404) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Card>
          <CardHeader>
            <CardTitle>笔记本不存在</CardTitle>
          </CardHeader>
          <CardContent>
            <Link to="/" className="text-sm text-primary hover:underline">
              返回首页
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }
  if (!detail.data) {
    return <p className="p-6 text-sm text-destructive">加载失败</p>;
  }

  const nb = detail.data;
  const notes = nb.notes ?? [];
  const selected = nb.sources.find((source) => source.video_id === selectedVideoId) ?? null;
  const openNote = notes.find((note) => note.id === openNoteId) ?? null;
  const browsingList = !selected;
  const listRows = mixSourceRows(nb.sources, notes);
  const previewMessage = mindMapNotice(preview.isLoading, preview.isError, preview.error, preview.data);
  const workbenchColumns = [
    leftCollapsed ? "3rem" : "minmax(15rem, 1fr)",
    "minmax(0, 2.2fr)",
    rightCollapsed ? "3rem" : "minmax(16rem, 2fr)",
  ].join(" ");

  async function discussMindMap(message: string) {
    const task = preview.data;
    if (!task || discussing.current) return;
    const videoIds = idList(task.params_json?.video_ids);
    const noteIds = idList(task.params_json?.note_ids);
    discussing.current = true;
    setRelay({
      pending: {
        id: -3,
        role: "user",
        content_text: message,
        citations: [],
        source_ids: videoIds,
        note_id: null,
        created_at: null,
      },
      live: {
        id: -4,
        role: "assistant",
        content_text: "",
        citations: [],
        source_ids: videoIds,
        note_id: null,
        created_at: null,
      },
      error: null,
    });
    let savedId: number | null = null;
    try {
      await readChatStream(token, notebookId, message, videoIds, {
        noteIds,
        onToken: (chunk) => {
          setRelay((current) =>
            current?.live
              ? { ...current, live: { ...current.live, content_text: current.live.content_text + chunk } }
              : current,
          );
        },
        onWarning: () => {
          setRelay((current) =>
            current?.live ? { ...current, live: { ...current.live, truncated: true } } : current,
          );
        },
        onError: (text) => {
          setRelay((current) => (current?.live ? { ...current, live: { ...current.live, error: text } } : current));
        },
        onDone: (messageId, citations) => {
          savedId = messageId;
          setRelay((current) =>
            current?.live
              ? { ...current, live: { ...current.live, id: messageId ?? current.live.id, citations } }
              : current,
          );
        },
      });
      await qc.invalidateQueries({ queryKey: ["chat", notebookId] });
      const fresh = qc.getQueryData<ChatMessage[]>(["chat", notebookId]) ?? [];
      setRelay((current) => {
        if (!current) return current;
        const pending = fresh.some((item) => item.role === "user" && item.content_text === message)
          ? null
          : current.pending;
        const live = savedId != null && fresh.some((item) => item.id === savedId) ? null : current.live;
        if (!pending && !live) return null;
        return { ...current, pending, live, error: null };
      });
    } catch (error) {
      setRelay({
        pending: null,
        live: null,
        error: error instanceof ApiError ? error.message : "发送失败",
      });
    } finally {
      discussing.current = false;
    }
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* 顶栏 */}
      <header className="app-header-shell flex shrink-0 items-center justify-between px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 rounded-full"
            onClick={() => navigate("/")}
            title="返回首页"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <span className="text-xl leading-none">{nb.icon || "📁"}</span>
          <h1 className="truncate text-base font-semibold tracking-tight">{nb.title}</h1>
          <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
            {nb.source_count} 个来源 · {nb.note_count} 条笔记
          </span>
        </div>
        <UserMenu
          onLogout={() => {
            logout();
            navigate("/login", { replace: true });
          }}
        />
      </header>

      {/* 三栏：圆角浮动面板（左右可折叠） */}
      <div
        className="notebook-workbench grid min-h-0 flex-1 gap-3 overflow-hidden p-3"
        style={{ gridTemplateColumns: workbenchColumns }}
      >
        {/* 左：来源 */}
        <aside
          className={cn(
            "panel-surface flex min-h-0 min-w-0 flex-col",
            leftCollapsed ? "overflow-hidden" : browsingList ? "overflow-y-auto" : "overflow-hidden",
          )}
        >
          {leftCollapsed ? (
            <SideRail
              side="left"
              label="来源"
              icon={Library}
              badge={nb.source_count || null}
              onExpand={() => setLeftCollapsed(false)}
            />
          ) : (
            <>
          <header className="panel-header">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Library className="h-3.5 w-3.5" />
              </span>
              <h2 className="text-sm font-semibold tracking-tight">来源</h2>
              <span className="panel-count">{nb.source_count}</span>
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 rounded-full hover:bg-primary/10 hover:text-primary"
              title="折叠来源"
              aria-label="折叠来源"
              onClick={() => setLeftCollapsed(true)}
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          </header>

          {selected ? (
            <SourceTranscript
              access={token}
              videoId={selected.video_id}
              title={selected.video.title || selected.video.source_url || `来源 ${selected.video_id}`}
              hasFile={!!selected.video.storage_key}
              overviewStatus={selected.video.overview_status}
              overviewText={selected.video.overview_text}
              overviewError={selected.video.overview_error}
              focusLineNo={focusCue?.videoId === selected.video_id ? focusCue.lineNo : null}
              onBack={() => setSelectedVideoId(null)}
            />
          ) : null}

          {/* 两按钮：添加来源 / 新建笔记 */}
          <div className={browsingList ? "flex gap-2 border-b border-border/40 px-3 py-3" : "hidden"}>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 rounded-full border-primary/25 bg-primary/5 text-primary hover:bg-primary/10 hover:text-primary"
              onClick={() => {
                setShowAddSource(true);
              }}
            >
              <Plus className="mr-1 h-3.5 w-3.5" /> 添加来源
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 rounded-full border-border/70"
              onClick={() => alert("笔记功能即将上线")}
              title="即将上线"
            >
              <Plus className="mr-1 h-3.5 w-3.5" /> 新建笔记
            </Button>
          </div>

          {/* 工具栏：filter + select all */}
          <div className={browsingList ? "flex items-center justify-between border-b border-border/40 px-3.5 py-2 text-xs text-muted-foreground" : "hidden"}>
            <span className="text-[11px]">
              已选 {nb.sources.filter((s) => s.selected_for_chat).length}/{nb.sources.length}
            </span>
            <SelectAll
              sources={nb.sources}
              onChange={(selected) => setSelection.mutate({ selected })}
            />
          </div>

          {/* 上传 / URL 弹窗（AddSourceDialog 在 portal 里渲染） */}
          <AddSourceDialog
            open={showAddSource}
            onOpenChange={setShowAddSource}
            uploading={upload.isPending || fetchUrl.isPending}
            uploadingMessage={
              upload.isPending
                ? "上传中…"
                : fetchUrl.isPending
                  ? "URL 添加中…"
                  : undefined
            }
            onUploadFiles={(files) => {
              for (const f of files) upload.mutate(f);
            }}
            onSubmitUrls={(urls) => {
              for (const u of urls) fetchUrl.mutate(u);
            }}
          />

          {browsingList && listRows.length === 0 ? (
            <div className="empty-panel">
              <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Library className="h-5 w-5" />
              </span>
              <p className="text-sm font-medium text-foreground">还没有来源</p>
              <p className="mt-1.5 max-w-[14rem] text-xs leading-relaxed text-muted-foreground">
                点上方「添加来源」，上传视频或粘贴链接。
              </p>
            </div>
          ) : null}
          {browsingList && listRows.length > 0 ? (
            <div className="space-y-1 p-2">
              {listRows.map((row) =>
                row.kind === "source" ? (
                  <SimpleSourceRow
                    key={`source-${row.source.video_id}`}
                    source={row.source}
                    active={selectedVideoId === row.source.video_id}
                    onOpen={() => {
                      setLeftCollapsed(false);
                      setFocusCue(null);
                      setSelectedVideoId(row.source.video_id);
                    }}
                    onRename={() =>
                      setRenameTarget({
                        kind: "source",
                        id: row.source.video_id,
                        title: row.source.video.title || "",
                      })
                    }
                    onRemove={() => {
                      if (window.confirm("删除这个来源？")) removeSource.mutate(row.source.video_id);
                    }}
                    onRegenerate={
                      row.source.video.status === "ready"
                        ? () => regenerate.mutate(row.source.video_id)
                        : undefined
                    }
                    onRetryFetch={
                      row.source.video.source_type === "url" &&
                      row.source.video.status !== "ready"
                        ? () => retryFetch.mutate(row.source.video_id)
                        : undefined
                    }
                    onCancelFetch={
                      row.source.video.source_type === "url" &&
                      (row.source.video.status === "pending" ||
                        row.source.video.status === "probing" ||
                        row.source.video.subtitle_status === "processing" ||
                        row.source.video.overview_status === "processing")
                        ? () => cancelFetch.mutate(row.source.video_id)
                        : undefined
                    }
                    onToggleSelected={(selectedFlag) =>
                      setSelection.mutate({ videoId: row.source.video_id, selected: selectedFlag })
                    }
                  />
                ) : (
                  <NoteRow
                    key={`note-${row.note.id}`}
                    note={row.note}
                    active={openNoteId === row.note.id}
                    onOpen={() => {
                      setRightCollapsed(false);
                      setOpenNoteId(row.note.id);
                    }}
                    onRename={() =>
                      setRenameTarget({ kind: "note", id: row.note.id, title: row.note.title })
                    }
                    onRemove={() => {
                      if (window.confirm("删除这条笔记？")) removeNote.mutate(row.note.id);
                    }}
                    onToggleSelected={(selectedFlag) =>
                      setNoteSelection.mutate({ noteId: row.note.id, selected: selectedFlag })
                    }
                  />
                ),
              )}
            </div>
          ) : null}
            </>
          )}
        </aside>

        <main className="panel-surface panel-surface-center flex min-h-0 min-w-0 flex-col overflow-hidden">
          <header className="panel-header">
            <div className="flex min-w-0 items-center gap-2">
              <h2 className="text-sm font-semibold tracking-tight">对话</h2>
              <span className="panel-count">
                {nb.sources.filter((s) => s.selected_for_chat).length + notes.filter((n) => n.selected_for_chat).length}
              </span>
            </div>
            <span className="hidden text-[11px] text-muted-foreground sm:inline">基于已勾选的来源与笔记</span>
          </header>
          <NotebookChat
            access={token}
            notebookId={notebookId}
            sources={nb.sources.map((source) => ({
              videoId: source.video_id,
              title: source.video.title || source.video.source_url || `来源 ${source.video_id}`,
              selected: source.selected_for_chat,
            }))}
            onJump={(videoId, lineNo) => {
              setLeftCollapsed(false);
              setSelectedVideoId(videoId);
              setFocusCue({ videoId, lineNo });
            }}
            relay={relay}
          />
        </main>

        <aside className="panel-surface relative flex min-h-0 min-w-0 flex-col overflow-hidden">
          {rightCollapsed ? (
            <StudioCollapsedRail
              access={token}
              notebookId={notebookId}
              onExpand={() => setRightCollapsed(false)}
              onOpenCapability={(capabilityId) => {
                setPreviewTaskId(null);
                setPreviewFormat(null);
                setPreviewExpanded(false);
                setOpenNoteId(null);
                setPendingCapabilityId(capabilityId);
                setRightCollapsed(false);
              }}
              onOpenTask={(taskId, formatKey) => {
                setOpenNoteId(null);
                setPendingCapabilityId(null);
                setPreviewExpanded(false);
                setPreviewFormat(formatKey);
                setPreviewTaskId(taskId);
                setRightCollapsed(false);
              }}
            />
          ) : (
            <>
              {openNote || previewTaskId != null ? (
                <Button
                  size="icon"
                  variant="outline"
                  className="absolute -left-3 top-1/2 z-20 h-7 w-7 -translate-y-1/2 rounded-full border-border/70 bg-card shadow-soft"
                  title="折叠 Studio"
                  aria-label="折叠 Studio"
                  onClick={() => setRightCollapsed(true)}
                >
                  <PanelRightClose className="h-3.5 w-3.5" />
                </Button>
              ) : null}
              {openNote ? (
                <StudioNote
                  note={openNote}
                  onOpenStudio={() => setOpenNoteId(null)}
                  onJump={(videoId, lineNo) => {
                    setLeftCollapsed(false);
                    setSelectedVideoId(videoId);
                    setFocusCue({ videoId, lineNo });
                  }}
                />
              ) : previewTaskId != null && previewFormat === "slides" ? (
                <StudioSlides
                  access={token}
                  taskId={previewTaskId}
                  title={preview.data?.title || "幻灯片"}
                  crumb={nb.title}
                  artifacts={preview.data?.artifacts ?? []}
                  pending={!preview.data && !preview.isError}
                  notice={
                    preview.isError
                      ? preview.error instanceof ApiError
                        ? preview.error.message
                        : "加载失败"
                      : null
                  }
                  videos={snapshotVideos(idList(preview.data?.params_json?.video_ids), nb.sources)}
                  notes={snapshotNotes(idList(preview.data?.params_json?.note_ids), notes)}
                  expanded={previewExpanded}
                  onBack={() => {
                    setPreviewTaskId(null);
                    setPreviewFormat(null);
                    setPreviewExpanded(false);
                  }}
                  onToggleExpanded={() => setPreviewExpanded((value) => !value)}
                  onOpenVideo={(videoId) => {
                    setPreviewExpanded(false);
                    setLeftCollapsed(false);
                    setFocusCue(null);
                    setSelectedVideoId(videoId);
                  }}
                  onOpenNote={(noteId) => {
                    setPreviewExpanded(false);
                    setRightCollapsed(false);
                    setOpenNoteId(noteId);
                  }}
                />
              ) : previewTaskId != null && previewFormat === "file" ? (
                <StudioFile
                  access={token}
                  taskId={previewTaskId}
                  title={preview.data?.title || "文件"}
                  artifactId={preview.data?.artifacts?.find((item) => item.role === "main")?.id ?? null}
                  filename={preview.data?.artifacts?.find((item) => item.role === "main")?.filename ?? null}
                  onBack={() => {
                    setPreviewTaskId(null);
                    setPreviewFormat(null);
                    setPreviewExpanded(false);
                  }}
                />
              ) : previewTaskId != null ? (
                <StudioMindmap
                  title={preview.data?.title || "导图"}
                  crumb={nb.title}
                  text={previewMessage ? null : (preview.data?.text_content ?? null)}
                  notice={previewMessage}
                  noticeError={preview.isError}
                  videos={snapshotVideos(idList(preview.data?.params_json?.video_ids), nb.sources)}
                  notes={snapshotNotes(idList(preview.data?.params_json?.note_ids), notes)}
                  expanded={previewExpanded}
                  onBack={() => {
                    setPreviewTaskId(null);
                    setPreviewFormat(null);
                    setPreviewExpanded(false);
                  }}
                  onToggleExpanded={() => setPreviewExpanded((value) => !value)}
                  onOpenVideo={(videoId) => {
                    setPreviewExpanded(false);
                    setLeftCollapsed(false);
                    setFocusCue(null);
                    setSelectedVideoId(videoId);
                  }}
                  onOpenNote={(noteId) => {
                    setPreviewExpanded(false);
                    setRightCollapsed(false);
                    setOpenNoteId(noteId);
                  }}
                  onDiscuss={(message) => {
                    void discussMindMap(message);
                  }}
                />
              ) : (
                <StudioHome
                  access={token}
                  notebookId={notebookId}
                  sources={nb.sources}
                  notes={notes}
                  pendingCapabilityId={pendingCapabilityId}
                  onPendingCapabilityHandled={() => setPendingCapabilityId(null)}
                  onCollapse={() => setRightCollapsed(true)}
                  onOpenTask={(taskId, formatKey) => {
                    setRightCollapsed(false);
                    setPreviewExpanded(false);
                    setPreviewFormat(formatKey);
                    setPreviewTaskId(taskId);
                  }}
                />
              )}
            </>
          )}
        </aside>
      </div>
      <SourceRenameDialog
        open={renameTarget !== null}
        title={renameTarget?.title || ""}
        heading={renameTarget?.kind === "note" ? "重命名笔记" : "重命名来源"}
        pending={rename.isPending || renameNote.isPending}
        error={
          (renameTarget?.kind === "note" ? renameNote.error : rename.error) instanceof ApiError
            ? ((renameTarget?.kind === "note" ? renameNote.error : rename.error) as ApiError).message
            : null
        }
        onClose={() => setRenameTarget(null)}
        onSubmit={(title) => {
          if (!renameTarget) return;
          if (renameTarget.kind === "note") renameNote.mutate({ noteId: renameTarget.id, title });
          else rename.mutate({ videoId: renameTarget.id, title });
        }}
      />
    </div>
  );
}

type SourceListRow =
  | { kind: "source"; at: string; source: SourceSummary }
  | { kind: "note"; at: string; note: NoteRead };

function mixSourceRows(sources: SourceSummary[], notes: NoteRead[]): SourceListRow[] {
  const rows: SourceListRow[] = [
    ...sources.map((source) => ({
      kind: "source" as const,
      at: source.video.created_at ?? "",
      source,
    })),
    ...notes.map((note) => ({ kind: "note" as const, at: note.created_at ?? "", note })),
  ];
  rows.sort((a, b) => a.at.localeCompare(b.at) || a.kind.localeCompare(b.kind));
  return rows;
}

function NoteRow({
  note,
  active,
  onOpen,
  onRename,
  onRemove,
  onToggleSelected,
}: {
  note: NoteRead;
  active: boolean;
  onOpen: () => void;
  onRename: () => void;
  onRemove: () => void;
  onToggleSelected: (selected: boolean) => void;
}) {
  return (
    <div className={`group source-card ${active ? "source-selected" : ""}`}>
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-[hsl(175_60%_94%)] text-[hsl(var(--success))]">
        <StickyNote className="h-3.5 w-3.5" />
      </div>
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onOpen}>
        <div className="line-clamp-2 text-[13px] font-medium leading-snug">{note.title}</div>
        <div className="mt-1">
          <span className="status-chip status-chip-ok">笔记</span>
        </div>
      </button>
      <SourceRowMenu onRename={onRename} onRemove={onRemove} />
      <input
        type="checkbox"
        className="mt-1.5 rounded"
        checked={note.selected_for_chat}
        onClick={(event) => event.stopPropagation()}
        onChange={() => onToggleSelected(!note.selected_for_chat)}
      />
    </div>
  );
}

function StudioHome({
  access,
  notebookId,
  sources,
  notes,
  onOpenTask,
  onCollapse,
  pendingCapabilityId,
  onPendingCapabilityHandled,
}: {
  access: string;
  notebookId: number;
  sources: SourceSummary[];
  notes: NoteRead[];
  onOpenTask: (taskId: number, formatKey: string) => void;
  onCollapse: () => void;
  pendingCapabilityId?: number | null;
  onPendingCapabilityHandled?: () => void;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="panel-header">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
          <h2 className="text-sm font-semibold tracking-tight">Studio</h2>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 rounded-full hover:bg-primary/10 hover:text-primary"
          title="折叠 Studio"
          aria-label="折叠 Studio"
          onClick={onCollapse}
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </header>
      <StudioPanel
        access={access}
        notebookId={notebookId}
        sources={sources}
        notes={notes}
        onOpenTask={onOpenTask}
        pendingCapabilityId={pendingCapabilityId}
        onPendingCapabilityHandled={onPendingCapabilityHandled}
      />
    </div>
  );
}

interface StudioArtifactRef {
  id: number;
  role: string;
  filename: string;
  mime: string;
}

interface StudioTaskDetail {
  id: number;
  title: string;
  status: string;
  format_key: string;
  text_content: string | null;
  pdf_error?: string | null;
  artifacts?: StudioArtifactRef[];
  params_json?: {
    video_ids?: unknown;
    note_ids?: unknown;
  };
}

function idList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is number => typeof item === "number");
}

function snapshotVideos(ids: number[], sources: SourceSummary[]): { id: number; title: string }[] {
  return ids.map((id) => {
    const source = sources.find((item) => item.video_id === id);
    return {
      id,
      title: source?.video.title || source?.video.source_url || `来源 ${id}`,
    };
  });
}

function snapshotNotes(ids: number[], notes: NoteRead[]): { id: number; title: string }[] {
  return ids.map((id) => ({
    id,
    title: notes.find((note) => note.id === id)?.title || `笔记 ${id}`,
  }));
}

function mindMapNotice(
  loading: boolean,
  failed: boolean,
  error: unknown,
  task: StudioTaskDetail | undefined,
): string | null {
  if (!task) {
    if (loading) return "加载导图…";
    if (error instanceof ApiError) return error.message;
    if (failed) return "加载失败";
    return "加载导图…";
  }
  if (task.text_content == null) return "没有导图内容";
  return null;
}

function StudioNote({
  note,
  onOpenStudio,
  onJump,
}: {
  note: NoteRead;
  onOpenStudio: () => void;
  onJump: (videoId: number, lineNo: number) => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyNote() {
    try {
      await navigator.clipboard.writeText(note.content_text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="panel-header">
        <p className="min-w-0 truncate text-xs text-muted-foreground">
          <button type="button" className="hover:text-foreground hover:underline" onClick={onOpenStudio}>
            Studio
          </button>
          <span className="px-1">›</span>
          <span className="text-foreground">笔记</span>
        </p>
        <div className="flex items-center gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 rounded-full"
            title={copied ? "已复制" : "复制"}
            onClick={() => void copyNote()}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button size="icon" variant="ghost" className="h-7 w-7 rounded-full" title="返回 Studio" onClick={onOpenStudio}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>
      <div className="flex shrink-0 items-start gap-2 px-4 pb-2 pt-3">
        <h2 className="min-w-0 flex-1 text-base font-semibold leading-6 tracking-tight">{note.title}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">
        <MarkdownMessage text={note.content_text} citations={note.citations ?? []} onJump={onJump} />
      </div>
    </div>
  );
}

function sourceBusy(video: VideoRead): boolean {
  return (
    video.status === "pending" ||
    video.status === "probing" ||
    video.subtitle_status === "processing" ||
    video.overview_status === "processing"
  );
}

function fetchLabel(video: VideoRead): string | null {
  if (video.status === "pending" || video.status === "probing") return "正在抓取…";
  if (video.status === "failed") return video.error_message || "抓取失败";
  return null;
}

function subtitleLabel(status: VideoRead["subtitle_status"]): string | null {
  if (status === "pending") return "等待生成字幕";
  if (status === "processing") return "正在生成字幕";
  if (status === "failed") return "字幕失败";
  return null;
}

function SelectAll({
  sources,
  onChange,
}: {
  sources: SourceSummary[];
  onChange: (selected: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const selectedCount = sources.filter((source) => source.selected_for_chat).length;
  const all = sources.length > 0 && selectedCount === sources.length;
  const some = selectedCount > 0 && !all;
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = some;
  }, [some]);
  return (
    <label className="flex cursor-pointer items-center gap-1.5">
      <input
        ref={ref}
        type="checkbox"
        className="rounded"
        checked={all}
        disabled={sources.length === 0}
        onChange={() => onChange(!all)}
      />
      <span>全选</span>
    </label>
  );
}

function SimpleSourceRow({
  source,
  active = false,
  onOpen,
  onRename,
  onRemove,
  onRegenerate,
  onRetryFetch,
  onCancelFetch,
  onToggleSelected,
}: {
  source: SourceSummary;
  active?: boolean;
  onOpen: () => void;
  onRename: () => void;
  onRemove: () => void;
  onRegenerate?: () => void;
  onRetryFetch?: () => void;
  onCancelFetch?: () => void;
  onToggleSelected: (selected: boolean) => void;
}) {
  const v = source.video;
  const busy = sourceBusy(v);
  const failed = v.status === "failed";
  const TypeIcon = v.source_type === "upload" ? UploadIcon : Link2;
  const fetch = fetchLabel(v);
  const sub = fetch ? null : subtitleLabel(v.subtitle_status);
  const meta = !fetch
    ? [fmtDuration(v.duration_ms), v.width && v.height ? `${v.width}×${v.height}` : null, fmtSize(v.size_bytes)]
        .filter(Boolean)
        .join(" · ")
    : null;
  return (
    <div className={`group source-card ${active ? "source-selected" : ""}`}>
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <TypeIcon className="h-3.5 w-3.5" />
      </div>
      <button
        type="button"
        className={`min-w-0 flex-1 text-left ${busy ? "cursor-default" : ""}`}
        onClick={() => {
          if (!busy && v.status === "ready") onOpen();
        }}
      >
        <div className="line-clamp-2 text-[13px] font-medium leading-snug">
          {v.title || v.source_url || `来源 ${v.id}`}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          {fetch ? (
            <span className="status-chip status-chip-busy">{fetch}</span>
          ) : failed ? (
            <span className="status-chip status-chip-fail">处理失败</span>
          ) : sub ? (
            <span className="status-chip status-chip-busy">{sub}</span>
          ) : v.subtitle_status === "ready" ? (
            <span className="status-chip status-chip-ok">字幕就绪</span>
          ) : (
            <span className="status-chip status-chip-idle">待处理</span>
          )}
          {meta ? <span className="text-[10px] text-muted-foreground">{meta}</span> : null}
        </div>
        {failed ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 rounded-xl border border-amber-200/80 bg-amber-50 px-2.5 py-1.5 text-[10px] text-amber-900">
            <span className="min-w-0 flex-1 leading-snug">处理遇到问题，可重试或稍后再看。</span>
            {onRetryFetch ? (
              <button
                type="button"
                className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 font-medium hover:bg-amber-200"
                onClick={(event) => {
                  event.stopPropagation();
                  onRetryFetch();
                }}
              >
                重试
              </button>
            ) : null}
          </div>
        ) : null}
      </button>
      <SourceRowMenu
        onRename={onRename}
        onRemove={onRemove}
        onRegenerate={onRegenerate}
        onRetryFetch={onRetryFetch}
        onCancelFetch={onCancelFetch}
        alwaysVisible={busy || Boolean(onRetryFetch) || Boolean(onCancelFetch)}
      />
      {busy ? (
        <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin status-busy" />
      ) : failed ? null : (
        <input
          type="checkbox"
          className="mt-1.5 rounded"
          checked={source.selected_for_chat}
          onClick={(event) => event.stopPropagation()}
          onChange={() => onToggleSelected(!source.selected_for_chat)}
        />
      )}
    </div>
  );
}
