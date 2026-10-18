import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Loader2, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SourceRenameDialog } from "@/components/source-row-menu";

const ERROR_LABELS: Record<string, string> = {
  timeout: "超时",
  process_failed: "进程失败",
  no_output: "没有主产物",
  format_mismatch: "格式不对",
};

type TextField = {
  type: "text";
  key: string;
  label?: string;
  required?: boolean;
  multiline?: boolean;
  placeholder?: string;
};

type FormField = { type: "language" } | { type: "sources" } | TextField;

interface Capability {
  id: number;
  name: string;
  icon: string | null;
  form_json: FormField[];
}

interface StudioTask {
  id: number;
  title: string;
  status: string;
  capability_id: number;
  format_key: string;
  error_code: string | null;
  created_at: string | null;
  params_json?: {
    video_ids?: unknown;
    note_ids?: unknown;
  };
}

export interface StudioSource {
  video_id: number;
  selected_for_chat: boolean;
  video: { title: string | null; source_url: string | null };
}

export interface StudioNote {
  id: number;
  title: string;
  selected_for_chat: boolean;
}

interface Draft {
  capability: Capability;
  language: "中文" | "English";
  videoIds: number[];
  noteIds: number[];
  fields: Record<string, string>;
}

function sourceTitle(source: StudioSource): string {
  return source.video.title || source.video.source_url || `来源 ${source.video_id}`;
}

function textFields(form: FormField[]): TextField[] {
  return form.filter((field): field is TextField => field.type === "text");
}

function toggleId(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

function idCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

function capabilityIcon(capabilities: Capability[] | undefined, task: StudioTask): string | null {
  return capabilities?.find((item) => item.id === task.capability_id)?.icon ?? null;
}

function sourceLabel(task: StudioTask): string {
  const count = idCount(task.params_json?.video_ids) + idCount(task.params_json?.note_ids);
  return count === 1 ? "1 source" : `${count} sources`;
}

function relativeTime(value: string | null): string {
  if (!value) return "";
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
  const then = new Date(hasZone ? value : `${value}Z`);
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (Number.isNaN(seconds)) return "";
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function StudioPanel({
  access,
  notebookId,
  sources,
  notes,
  onOpenTask,
}: {
  access: string;
  notebookId: number;
  sources: StudioSource[];
  notes: StudioNote[];
  onOpenTask?: (taskId: number, formatKey: string) => void;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [renameTask, setRenameTask] = useState<StudioTask | null>(null);

  const capabilities = useQuery({
    queryKey: ["studio-capabilities", notebookId],
    queryFn: () => api<Capability[]>(`/notebooks/${notebookId}/studio/capabilities`, { access }),
    enabled: !!access && !!notebookId,
  });

  const tasks = useQuery({
    queryKey: ["studio-tasks", notebookId],
    queryFn: () => api<StudioTask[]>(`/notebooks/${notebookId}/studio/tasks`, { access }),
    enabled: !!access && !!notebookId,
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      return rows.some((task) => task.status === "queued" || task.status === "running") ? 2000 : false;
    },
  });

  const createTask = useMutation({
    mutationFn: (body: {
      capability_id: number;
      language?: string;
      video_ids: number[];
      note_ids: number[];
      fields: Record<string, string>;
    }) => api(`/notebooks/${notebookId}/studio/tasks`, { method: "POST", access, body }),
    onSuccess: () => {
      setDraft(null);
      setFormError(null);
      void qc.invalidateQueries({ queryKey: ["studio-tasks", notebookId] });
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "创建失败");
    },
  });

  const removeTask = useMutation({
    mutationFn: (taskId: number) => api(`/studio/tasks/${taskId}`, { method: "DELETE", access, raw: true }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["studio-tasks", notebookId] }),
  });

  const rename = useMutation({
    mutationFn: ({ taskId, title }: { taskId: number; title: string }) =>
      api<StudioTask>(`/studio/tasks/${taskId}`, { method: "PATCH", access, body: { title } }),
    onSuccess: () => {
      setRenameTask(null);
      void qc.invalidateQueries({ queryKey: ["studio-tasks", notebookId] });
      void qc.invalidateQueries({ queryKey: ["studio-task", notebookId] });
    },
  });

  async function downloadSlides(task: StudioTask) {
    const detail = await api<{
      title: string;
      artifacts?: { id: number; role: string; filename: string }[];
    }>(`/studio/tasks/${task.id}`, { access });
    const artifact = detail.artifacts?.find((item) => item.role === "main");
    if (!artifact) {
      setFormError("没有幻灯片文件");
      return;
    }
    const signed = await api<{ url: string }>(`/studio/tasks/${task.id}/artifacts/${artifact.id}`, { access });
    const link = document.createElement("a");
    link.href = signed.url;
    link.download = artifact.filename || `${detail.title || task.title}.pptx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  async function downloadMindMap(task: StudioTask) {
    const detail = await api<{ title: string; text_content: string | null }>(`/studio/tasks/${task.id}`, {
      access,
    });
    if (!detail.text_content) {
      setFormError("没有导图内容");
      return;
    }
    const blob = new Blob([detail.text_content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${detail.title || task.title}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function openCapability(capability: Capability) {
    const fields: Record<string, string> = {};
    for (const field of textFields(capability.form_json ?? [])) fields[field.key] = "";
    setFormError(null);
    setDraft({
      capability,
      language: "中文",
      videoIds: sources.filter((source) => source.selected_for_chat).map((source) => source.video_id),
      noteIds: notes.filter((note) => note.selected_for_chat).map((note) => note.id),
      fields,
    });
  }

  function submitDraft() {
    if (!draft || createTask.isPending) return;
    const form = draft.capability.form_json ?? [];
    const hasLanguage = form.some((field) => field.type === "language");
    const hasSources = form.some((field) => field.type === "sources");
    for (const field of textFields(form)) {
      if (field.required && !(draft.fields[field.key] ?? "").trim()) {
        setFormError("必填文本不能为空");
        return;
      }
    }
    if (hasSources && draft.videoIds.length === 0 && draft.noteIds.length === 0) {
      setFormError("请选择来源");
      return;
    }
    createTask.mutate({
      capability_id: draft.capability.id,
      ...(hasLanguage ? { language: draft.language } : {}),
      video_ids: hasSources ? draft.videoIds : [],
      note_ids: hasSources ? draft.noteIds : [],
      fields: draft.fields,
    });
  }

  const taskRows = tasks.data ?? [];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="grid grid-cols-2 gap-2 p-3">
        {(capabilities.data ?? []).map((capability) => (
          <button
            key={capability.id}
            type="button"
            className="flex items-center gap-2 rounded-full border border-border/60 bg-muted/30 px-3 py-2 text-left text-xs transition-colors hover:bg-muted/60"
            onClick={() => openCapability(capability)}
          >
            {capability.icon ? <span className="shrink-0">{capability.icon}</span> : null}
            <span className="line-clamp-2">{capability.name}</span>
          </button>
        ))}
      </div>
      {capabilities.error instanceof ApiError ? (
        <p className="px-4 text-xs text-destructive">{capabilities.error.message}</p>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {taskRows.length === 0 && !tasks.isLoading ? (
          <p className="px-4 text-xs text-muted-foreground">从左侧点开笔记，会在这里查看。</p>
        ) : null}
        <div className="divide-y">
          {taskRows.map((task) => {
            const busy = task.status === "queued" || task.status === "running";
            const errorLabel =
              task.status === "failed" ? ERROR_LABELS[task.error_code ?? ""] ?? task.error_code : null;
            const openable =
              task.status === "succeeded" &&
              (task.format_key === "mind_map" || task.format_key === "slides" || task.format_key === "file") &&
              !!onOpenTask;
            const icon = capabilityIcon(capabilities.data, task);
            if (task.format_key === "mind_map" || task.format_key === "slides") {
              const when = relativeTime(task.created_at);
              const meta = [sourceLabel(task), when].filter(Boolean).join(" · ");
              return (
                <div key={task.id} className="group flex items-start gap-2.5 rounded-xl px-3 py-2.5 mx-1 transition-colors hover:bg-muted/50">
                  {icon ? (
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center text-base leading-none">
                      {icon}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className={`min-w-0 flex-1 text-left ${openable ? "" : "cursor-default"}`}
                    onClick={() => {
                      if (openable) onOpenTask?.(task.id, task.format_key);
                    }}
                  >
                    <div className="line-clamp-2 text-sm font-medium">{task.title}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {task.status === "failed" && errorLabel ? `${errorLabel} · ${meta}` : meta}
                    </div>
                  </button>
                  {busy ? <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" /> : null}
                  <TaskMenu
                    onRename={() => setRenameTask(task)}
                    onRemove={() => {
                      const label = task.format_key === "slides" ? "删除这个幻灯片？" : "删除这个导图？";
                      if (window.confirm(label)) removeTask.mutate(task.id);
                    }}
                    onDownload={
                      task.status !== "succeeded"
                        ? undefined
                        : () => void (task.format_key === "slides" ? downloadSlides(task) : downloadMindMap(task))
                    }
                  />
                </div>
              );
            }
            return (
              <div key={task.id} className="mx-1 flex items-start gap-2.5 rounded-xl px-3 py-2.5 transition-colors hover:bg-muted/50">
                {icon ? (
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center text-base leading-none">
                    {icon}
                  </span>
                ) : null}
                <div className="min-w-0 flex-1">
                  {openable ? (
                    <button
                      type="button"
                      className="line-clamp-2 text-left text-xs font-medium hover:underline"
                      onClick={() => onOpenTask?.(task.id, task.format_key)}
                    >
                      {task.title}
                    </button>
                  ) : (
                    <div className="line-clamp-2 text-xs font-medium">
                      {task.status === "failed" && errorLabel ? errorLabel : task.title}
                    </div>
                  )}
                </div>
                {busy ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-muted-foreground" /> : null}
                <button
                  type="button"
                  className="shrink-0 text-[10px] text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    if (window.confirm("删除这个任务？")) removeTask.mutate(task.id);
                  }}
                >
                  删除
                </button>
              </div>
            );
          })}
        </div>
      </div>
      <SourceRenameDialog
        open={renameTask !== null}
        title={renameTask?.title || ""}
        heading={renameTask?.format_key === "slides" ? "重命名幻灯片" : "重命名导图"}
        pending={rename.isPending}
        error={rename.error instanceof ApiError ? rename.error.message : null}
        onClose={() => {
          if (!rename.isPending) setRenameTask(null);
        }}
        onSubmit={(title) => {
          if (!renameTask) return;
          rename.mutate({ taskId: renameTask.id, title });
        }}
      />
      {draft ? (
        <CapabilityDialog
          draft={draft}
          sources={sources}
          notes={notes}
          pending={createTask.isPending}
          error={formError}
          onClose={() => {
            if (!createTask.isPending) setDraft(null);
          }}
          onChange={setDraft}
          onSubmit={submitDraft}
        />
      ) : null}
    </div>
  );
}

function TaskMenu({
  onRename,
  onRemove,
  onDownload,
}: {
  onRename: () => void;
  onRemove: () => void;
  onDownload?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
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

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        title="更多"
        className="rounded-full p-1 text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
        onClick={(event) => {
          event.stopPropagation();
          const rect = triggerRef.current?.getBoundingClientRect();
          if (rect) {
            const menuWidth = 148;
            const left = Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8));
            setAnchor({ top: rect.bottom + 6, left });
          }
          setOpen(true);
        }}
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      {open && anchor
        ? createPortal(
            <div className="fixed inset-0 z-50" onClick={() => setOpen(false)}>
              <div
                role="menu"
                className="absolute w-[148px] overflow-hidden rounded-xl border bg-popover py-1 text-popover-foreground shadow-lg"
                style={{ top: anchor.top, left: anchor.left }}
                onClick={(event) => event.stopPropagation()}
              >
                <MenuItem
                  icon={<Pencil className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setOpen(false);
                    onRename();
                  }}
                >
                  重命名
                </MenuItem>
                <MenuItem
                  icon={<Trash2 className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setOpen(false);
                    onRemove();
                  }}
                >
                  删除
                </MenuItem>
                {onDownload ? (
                  <MenuItem
                    icon={<Download className="h-3.5 w-3.5" />}
                    onClick={() => {
                      setOpen(false);
                      onDownload();
                    }}
                  >
                    下载
                  </MenuItem>
                ) : null}
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
  children,
}: {
  icon: ReactNode;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted"
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  );
}

function CapabilityDialog({
  draft,
  sources,
  notes,
  pending,
  error,
  onClose,
  onChange,
  onSubmit,
}: {
  draft: Draft;
  sources: StudioSource[];
  notes: StudioNote[];
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onChange: (draft: Draft) => void;
  onSubmit: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const form = draft.capability.form_json ?? [];

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <form
        className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-lg border bg-background p-4 shadow-xl"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
          {draft.capability.icon ? <span>{draft.capability.icon}</span> : null}
          {draft.capability.name}
        </h2>
        <div className="space-y-3">
          {form.map((field) => {
            if (field.type === "language") {
              return (
                <label key="language" className="block text-xs">
                  <span className="mb-1 block text-muted-foreground">语言</span>
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={draft.language}
                    onChange={(event) =>
                      onChange({
                        ...draft,
                        language: event.target.value === "English" ? "English" : "中文",
                      })
                    }
                  >
                    <option value="中文">中文</option>
                    <option value="English">English</option>
                  </select>
                </label>
              );
            }
            if (field.type === "sources") {
              return (
                <fieldset key="sources" className="text-xs">
                  <legend className="mb-1 text-muted-foreground">来源</legend>
                  <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
                    {sources.map((source) => (
                      <label key={`video-${source.video_id}`} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          className="rounded"
                          checked={draft.videoIds.includes(source.video_id)}
                          onChange={() =>
                            onChange({ ...draft, videoIds: toggleId(draft.videoIds, source.video_id) })
                          }
                        />
                        <span className="line-clamp-1">{sourceTitle(source)}</span>
                      </label>
                    ))}
                    {notes.map((note) => (
                      <label key={`note-${note.id}`} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          className="rounded"
                          checked={draft.noteIds.includes(note.id)}
                          onChange={() => onChange({ ...draft, noteIds: toggleId(draft.noteIds, note.id) })}
                        />
                        <span className="line-clamp-1">{note.title}</span>
                      </label>
                    ))}
                    {sources.length === 0 && notes.length === 0 ? (
                      <p className="text-muted-foreground">还没有来源</p>
                    ) : null}
                  </div>
                </fieldset>
              );
            }
            const value = draft.fields[field.key] ?? "";
            return (
              <label key={field.key} className="block text-xs">
                <span className="mb-1 block text-muted-foreground">
                  {field.label || field.key}
                  {field.required ? " *" : ""}
                </span>
                {field.multiline ? (
                  <textarea
                    className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder={field.placeholder}
                    value={value}
                    onChange={(event) =>
                      onChange({ ...draft, fields: { ...draft.fields, [field.key]: event.target.value } })
                    }
                  />
                ) : (
                  <Input
                    value={value}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      onChange({ ...draft, fields: { ...draft.fields, [field.key]: event.target.value } })
                    }
                  />
                )}
              </label>
            );
          })}
        </div>
        {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={pending}>
            取消
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? "提交中…" : "创建"}
          </Button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
