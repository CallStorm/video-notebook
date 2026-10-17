import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
  format_key: string;
  error_code: string | null;
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

export function StudioPanel({
  access,
  notebookId,
  sources,
  notes,
  onOpenMindMap,
}: {
  access: string;
  notebookId: number;
  sources: StudioSource[];
  notes: StudioNote[];
  onOpenMindMap?: (taskId: number) => void;
}) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

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
            className="flex items-center gap-2 rounded-full border px-3 py-2 text-left text-xs hover:bg-muted/60"
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
            const openable = task.status === "succeeded" && task.format_key === "mind_map" && !!onOpenMindMap;
            return (
              <div key={task.id} className="flex items-start gap-2 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  {openable ? (
                    <button
                      type="button"
                      className="line-clamp-2 text-left text-xs font-medium hover:underline"
                      onClick={() => onOpenMindMap(task.id)}
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
