import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Loader2, MoreVertical, PanelRightOpen, Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SourceRenameDialog } from "@/components/source-row-menu";
import { isStudioFormatVisible, isStudioOpenableFormat, isTextStudioFormat } from "@/studio/plugins/registry";

const ERROR_LABELS: Record<string, string> = {
  timeout: "超时",
  process_failed: "进程失败",
  no_output: "没有主产物",
  format_mismatch: "格式不对",
};

function failureLabel(task: { error_code: string | null; error_message?: string | null }): string | null {
  if (!task.error_code) return null;
  const base = ERROR_LABELS[task.error_code] ?? task.error_code;
  const msg = (task.error_message || "").trim();
  if (task.error_code === "timeout") {
    const m = msg.match(/超时上限\s*(\d+)\s*秒/);
    if (m) return `超时（已达 ${m[1]} 秒上限）`;
    return "超时（可在后台智能体提高超时）";
  }
  return base;
}


type TextField = {
  type: "text";
  key: string;
  label?: string;
  required?: boolean;
  multiline?: boolean;
  placeholder?: string;
};

type SelectOption = { value: string; label: string };

type SelectField = {
  type: "select";
  key: string;
  label?: string;
  required?: boolean;
  default?: string;
  options: SelectOption[];
};

type ValueField = TextField | SelectField;

type FormField = { type: "language" } | { type: "sources" } | ValueField;

interface Capability {
  id: number;
  name: string;
  icon: string | null;
  format_key: string;
  form_json: FormField[];
}

interface StudioTask {
  id: number;
  title: string;
  status: string;
  capability_id: number;
  format_key: string;
  error_code: string | null;
  error_message?: string | null;
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

function valueFields(form: FormField[]): ValueField[] {
  return form.filter((field): field is ValueField => field.type === "text" || field.type === "select");
}

function defaultFieldValue(field: ValueField): string {
  if (field.type === "select") {
    if (field.default) return field.default;
    return field.options[0]?.value ?? "";
  }
  return "";
}

function toggleId(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

function idCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}


function looksLikeBriefTitle(title: string): boolean {
  const t = title.trim();
  if (!t) return false;
  if (t.includes("\n") && t.length > 40) return true;
  const head = t.slice(0, 120);
  return ["受众", "结构建议", "页数", "主题：", "主题:", "要点：", "要点:"].some((m) => head.includes(m));
}

function shortTitleFromBriefish(title: string, maxLen = 24): string {
  const t = title.trim();
  for (const line of t.split("\n")) {
    const s = line.trim();
    for (const prefix of ["主题：", "主题:"]) {
      if (s.startsWith(prefix)) {
        const theme = s.slice(prefix.length).trim();
        if (theme) return theme.length > maxLen ? theme.slice(0, maxLen) + "…" : theme;
      }
    }
  }
  const first = t.split("\n").map((l) => l.trim()).find((l) => l && !/^(受众|结构建议|页数|要点|结论)/.test(l));
  const base = (first || t).replace(/\s+/g, " ");
  return base.length > maxLen ? base.slice(0, maxLen) + "…" : base;
}

/** List/rail label: never show a pasted brief as the card title. */
export function displayStudioTaskTitle(title: string | null | undefined): string {
  const raw = (title || "").trim() || "未命名";
  if (looksLikeBriefTitle(raw)) return shortTitleFromBriefish(raw);
  if (raw.length > 40) return raw.slice(0, 24) + "…";
  return raw;
}

function capabilityIcon(capabilities: Capability[] | undefined, task: StudioTask): string | null {
  return capabilities?.find((item) => item.id === task.capability_id)?.icon ?? null;
}

function sourceLabel(task: StudioTask): string {
  const count = idCount(task.params_json?.video_ids) + idCount(task.params_json?.note_ids);
  return count === 1 ? "1 个来源" : `${count} 个来源`;
}

function formatShortLabel(formatKey: string): string {
  if (formatKey === "slides") return "幻";
  if (formatKey === "four_panel") return "漫";
  if (formatKey === "file") return "文";
  return "导";
}

function deleteConfirmLabel(formatKey: string): string {
  if (formatKey === "slides") return "删除这个幻灯片？";
  if (formatKey === "four_panel") return "删除这个四格漫？";
  return "删除这个导图？";
}

function renameHeading(formatKey: string): string {
  if (formatKey === "slides") return "重命名幻灯片";
  if (formatKey === "four_panel") return "重命名四格漫";
  return "重命名导图";
}


function taskStatusChip(status: string): { label: string; className: string } | null {
  if (status === "queued") return { label: "排队中", className: "status-chip status-chip-idle" };
  if (status === "running") return { label: "生成中", className: "status-chip status-chip-busy" };
  if (status === "succeeded") return { label: "已完成", className: "status-chip status-chip-ok" };
  if (status === "failed") return { label: "失败", className: "status-chip status-chip-fail" };
  return null;
}

function relativeTime(value: string | null): string {
  if (!value) return "";
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
  const then = new Date(hasZone ? value : `${value}Z`);
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (Number.isNaN(seconds)) return "";
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  return `${Math.floor(seconds / 86400)} 天前`;
}

export function StudioCollapsedRail({
  access,
  notebookId,
  onExpand,
  onOpenTask,
}: {
  access: string;
  notebookId: number;
  onExpand: () => void;
  onOpenTask: (taskId: number, formatKey: string) => void;
}) {
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

  const taskRows = (tasks.data ?? []).filter((t) => isStudioFormatVisible(t.format_key));

  return (
    <div className="panel-rail">
      <Button
        size="icon"
        variant="ghost"
        className="h-8 w-8 shrink-0 rounded-full hover:bg-primary/10 hover:text-primary"
        title="展开产物"
        aria-label="展开产物"
        onClick={onExpand}
      >
        <PanelRightOpen className="h-4 w-4" />
      </Button>
      <div className="flex min-h-0 w-full flex-1 flex-col items-center gap-1 overflow-y-auto pb-2">
        <span className="pt-1 text-[9px] font-medium tracking-wide text-muted-foreground">产物</span>
        {taskRows.length === 0 && !tasks.isLoading ? (
          <span className="px-1 text-center text-[9px] leading-tight text-muted-foreground/80">暂无</span>
        ) : null}
        {taskRows.map((task) => {
          const busy = task.status === "queued" || task.status === "running";
          const openable =
            task.status === "succeeded" &&
            isStudioOpenableFormat(task.format_key);
          const icon = capabilityIcon(capabilities.data, task);
          const chip = taskStatusChip(task.status);
          const shown = displayStudioTaskTitle(task.title);
          const tip = chip ? `${shown} · ${chip.label}` : shown;
          return (
            <button
              key={task.id}
              type="button"
              className="panel-rail-icon relative"
              title={tip}
              aria-label={tip}
              onClick={() => {
                if (openable) onOpenTask(task.id, task.format_key);
                else onExpand();
              }}
            >
              {icon ? (
                <span className="text-base leading-none">{icon}</span>
              ) : (
                <span className="text-[10px] font-semibold text-muted-foreground">
                  {formatShortLabel(task.format_key)}
                </span>
              )}
              {busy ? (
                <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3 items-center justify-center rounded-full bg-card">
                  <Loader2 className="h-2.5 w-2.5 animate-spin text-primary" />
                </span>
              ) : null}
              {task.status === "failed" ? (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-destructive" />
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}


export function StudioPanel({
  access,
  notebookId,
  sources,
  notes,
  onOpenTask,
  onGoKnowledge,
  pendingCapabilityId = null,
  onPendingCapabilityHandled,
}: {
  access: string;
  notebookId: number;
  sources: StudioSource[];
  notes: StudioNote[];
  onOpenTask?: (taskId: number, formatKey: string) => void;
  onGoKnowledge?: () => void;
  pendingCapabilityId?: number | null;
  onPendingCapabilityHandled?: () => void;
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

  async function downloadFourPanel(task: StudioTask) {
    const detail = await api<{ title: string; text_content: string | null }>(`/studio/tasks/${task.id}`, {
      access,
    });
    if (!detail.text_content) {
      setFormError("没有可下载的四格漫内容");
      return;
    }
    const blob = new Blob([detail.text_content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${detail.title || task.title}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }


  async function downloadMindMap(task: StudioTask) {
    const detail = await api<{ title: string; text_content: string | null }>(`/studio/tasks/${task.id}`, {
      access,
    });
    if (!detail.text_content) {
      setFormError("没有可下载的文本内容");
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
    for (const field of valueFields(capability.form_json ?? [])) {
      fields[field.key] = defaultFieldValue(field);
    }
    setFormError(null);
    setDraft({
      capability,
      language: "中文",
      videoIds: sources.filter((source) => source.selected_for_chat).map((source) => source.video_id),
      noteIds: notes.filter((note) => note.selected_for_chat).map((note) => note.id),
      fields,
    });
  }

  useEffect(() => {
    if (pendingCapabilityId == null) return;
    const capability = (capabilities.data ?? []).find((item) => item.id === pendingCapabilityId);
    if (!capability || !isStudioFormatVisible(capability.format_key)) {
      if (capabilities.isFetched) onPendingCapabilityHandled?.();
      return;
    }
    openCapability(capability);
    onPendingCapabilityHandled?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open once when pending id arrives
  }, [pendingCapabilityId, capabilities.data, capabilities.isFetched]);

  function submitDraft() {
    if (!draft || createTask.isPending) return;
    const form = draft.capability.form_json ?? [];
    const hasLanguage = form.some((field) => field.type === "language");
    const hasSources = form.some((field) => field.type === "sources");
    for (const field of valueFields(form)) {
      if (field.required && !(draft.fields[field.key] ?? "").trim()) {
        setFormError(field.type === "select" ? "必填选项不能为空" : "必填文本不能为空");
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

  const taskRows = (tasks.data ?? []).filter((t) => isStudioFormatVisible(t.format_key));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {capabilities.error instanceof ApiError ? (
        <p className="px-4 pt-3 text-xs text-destructive">{capabilities.error.message}</p>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {taskRows.length === 0 && !tasks.isLoading ? (
          <div className="empty-panel mx-3 mb-3 mt-6 py-8">
            <p className="text-sm font-medium text-foreground">还没有产物</p>
            <p className="mt-1.5 max-w-[16rem] text-xs leading-relaxed text-muted-foreground">
              在知识里勾选要点后生成导图或幻灯片。
            </p>
            {onGoKnowledge ? (
              <button
                type="button"
                className="mt-3 text-xs font-medium text-primary hover:underline"
                onClick={onGoKnowledge}
              >
                去知识
              </button>
            ) : null}
          </div>
        ) : null}
        <div className="pb-3 pt-2">
          {taskRows.map((task) => {
            const busy = task.status === "queued" || task.status === "running";
            const errorLabel =
              task.status === "failed" ? failureLabel(task) : null;
            const openable =
              task.status === "succeeded" &&
              (isStudioOpenableFormat(task.format_key)) &&
              !!onOpenTask;
            const icon = capabilityIcon(capabilities.data, task);
            if (isTextStudioFormat(task.format_key) || task.format_key === "slides") {
              const when = relativeTime(task.created_at);
              const meta = [sourceLabel(task), when].filter(Boolean).join(" · ");
              const chip = taskStatusChip(task.status);
              return (
                <div key={task.id} className="group task-card">
                  {icon ? (
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-muted/70 text-base leading-none">
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
                    <div className="line-clamp-2 text-[13px] font-medium leading-snug">{displayStudioTaskTitle(task.title)}</div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {chip ? <span className={chip.className}>{chip.label}</span> : null}
                      {task.status === "failed" && errorLabel ? (
                        <span className="text-[10px] text-amber-800">{errorLabel}</span>
                      ) : null}
                      {meta ? <span className="text-[10px] text-muted-foreground">{meta}</span> : null}
                    </div>
                  </button>
                  {busy ? <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin status-busy" /> : null}
                  <TaskMenu
                    onRename={() => setRenameTask(task)}
                    onRemove={() => {
                      const label = deleteConfirmLabel(task.format_key);
                      if (window.confirm(label)) removeTask.mutate(task.id);
                    }}
                    onDownload={
                      task.status !== "succeeded"
                        ? undefined
                        : () =>
                        void (task.format_key === "slides"
                          ? downloadSlides(task)
                          : task.format_key === "four_panel"
                            ? downloadFourPanel(task)
                            : downloadMindMap(task))
                    }
                  />
                </div>
              );
            }
            const chip = taskStatusChip(task.status);
            return (
              <div key={task.id} className="group task-card">
                {icon ? (
                  <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-muted/70 text-base leading-none">
                    {icon}
                  </span>
                ) : null}
                <div className="min-w-0 flex-1">
                  {openable ? (
                    <button
                      type="button"
                      className="line-clamp-2 text-left text-[13px] font-medium leading-snug hover:underline"
                      onClick={() => onOpenTask?.(task.id, task.format_key)}
                    >
                      {displayStudioTaskTitle(task.title)}
                    </button>
                  ) : (
                    <div className="line-clamp-2 text-[13px] font-medium leading-snug">
                      {displayStudioTaskTitle(task.title)}
                    </div>
                  )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {chip ? <span className={chip.className}>{chip.label}</span> : null}
                    {task.status === "failed" && errorLabel ? (
                      <span className="text-[10px] text-amber-800">{errorLabel}</span>
                    ) : null}
                  </div>
                </div>
                {busy ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin status-busy" /> : null}
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
        heading={renameTask ? renameHeading(renameTask.format_key) : "重命名"}
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
            <div className="fixed inset-0 z-[200]" onClick={() => setOpen(false)}>
              <div
                role="menu"
                className="absolute w-[148px] overflow-hidden rounded-xl border border-border/80 bg-popover py-1 text-popover-foreground shadow-lg"
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
        className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border/70 bg-card p-5 shadow-xl"
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
            if (field.type === "select") {
              const value = draft.fields[field.key] ?? defaultFieldValue(field);
              return (
                <label key={field.key} className="block text-xs">
                  <span className="mb-1 block text-muted-foreground">
                    {field.label || field.key}
                    {field.required ? " *" : ""}
                  </span>
                  <select
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={value}
                    onChange={(event) =>
                      onChange({ ...draft, fields: { ...draft.fields, [field.key]: event.target.value } })
                    }
                  >
                    {field.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
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
