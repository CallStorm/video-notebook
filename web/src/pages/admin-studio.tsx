import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AdminEmptyState,
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
  AdminTableShell,
} from "@/components/admin-shell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface FormatRead {
  key: string;
  label: string;
}

interface AgentRead {
  id: number;
  name: string;
  is_active: boolean;
}

interface CapabilityRead {
  id: number;
  name: string;
  icon: string | null;
  format_key: string;
  agent_id: number | null;
  enabled: boolean;
  is_builtin: boolean;
  form_json: unknown;
  created_at: string | null;
  updated_at: string | null;
}

type SourcesField = { type: "sources" };
type LanguageField = { type: "language" };
type TextField = {
  type: "text";
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  multiline: boolean;
};
type SelectOption = { value: string; label: string };
type SelectField = {
  type: "select";
  key: string;
  label: string;
  required: boolean;
  default?: string;
  options: SelectOption[];
};
type FormField = SourcesField | LanguageField | TextField | SelectField;

interface CapabilityFormState {
  name: string;
  icon: string;
  format_key: string;
  agent_id: number | null;
  form: FormField[];
}

const EMPTY_FORM: CapabilityFormState = {
  name: "",
  icon: "",
  format_key: "",
  agent_id: null,
  form: [],
};

const SELECT_CLASS = "admin-select";

function parseForm(raw: unknown): FormField[] {
  if (!Array.isArray(raw)) return [];
  const out: FormField[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    if (rec.type === "sources") out.push({ type: "sources" });
    else if (rec.type === "language") out.push({ type: "language" });
    else if (rec.type === "text") {
      out.push({
        type: "text",
        key: typeof rec.key === "string" ? rec.key : "",
        label: typeof rec.label === "string" ? rec.label : "",
        placeholder: typeof rec.placeholder === "string" ? rec.placeholder : "",
        required: Boolean(rec.required),
        multiline: Boolean(rec.multiline),
      });
    } else if (rec.type === "select") {
      const optionsRaw = Array.isArray(rec.options) ? rec.options : [];
      const options: SelectOption[] = [];
      for (const opt of optionsRaw) {
        if (!opt || typeof opt !== "object") continue;
        const o = opt as Record<string, unknown>;
        if (typeof o.value !== "string" || !o.value) continue;
        options.push({
          value: o.value,
          label: typeof o.label === "string" && o.label ? o.label : o.value,
        });
      }
      const item: SelectField = {
        type: "select",
        key: typeof rec.key === "string" ? rec.key : "",
        label: typeof rec.label === "string" ? rec.label : "",
        required: Boolean(rec.required),
        options,
      };
      if (typeof rec.default === "string" && rec.default) item.default = rec.default;
      out.push(item);
    }
  }
  return out;
}

function toApiForm(fields: FormField[]): Record<string, unknown>[] {
  return fields.map((field) => {
    if (field.type === "sources" || field.type === "language") return { type: field.type };
    if (field.type === "select") {
      const item: Record<string, unknown> = {
        type: "select",
        key: field.key,
        label: field.label,
        required: field.required,
        options: field.options,
      };
      if (field.default) item.default = field.default;
      return item;
    }
    const item: Record<string, unknown> = {
      type: "text",
      key: field.key,
      label: field.label,
      required: field.required,
      multiline: field.multiline,
    };
    if (field.placeholder) item.placeholder = field.placeholder;
    return item;
  });
}

async function listFormats(access: string): Promise<FormatRead[]> {
  return api<FormatRead[]>("/admin/studio/formats", { access });
}

async function listAgents(access: string): Promise<AgentRead[]> {
  return api<AgentRead[]>("/admin/agents", { access });
}

async function listCapabilities(access: string): Promise<CapabilityRead[]> {
  return api<CapabilityRead[]>("/admin/studio/capabilities", { access });
}

async function createCapability(
  access: string,
  form: CapabilityFormState,
): Promise<CapabilityRead> {
  return api<CapabilityRead>("/admin/studio/capabilities", {
    method: "POST",
    access,
    body: {
      name: form.name,
      icon: form.icon.trim() || null,
      format_key: form.format_key,
      agent_id: form.agent_id,
      form: toApiForm(form.form),
    },
  });
}

async function updateCapability(
  access: string,
  id: number,
  form: CapabilityFormState,
): Promise<CapabilityRead> {
  return api<CapabilityRead>(`/admin/studio/capabilities/${id}`, {
    method: "PATCH",
    access,
    body: {
      name: form.name,
      icon: form.icon.trim() || null,
      agent_id: form.agent_id,
      form: toApiForm(form.form),
    },
  });
}

async function disableCapability(access: string, id: number): Promise<CapabilityRead> {
  return api<CapabilityRead>(`/admin/studio/capabilities/${id}/disable`, {
    method: "POST",
    access,
  });
}

async function enableCapability(access: string, id: number): Promise<CapabilityRead> {
  return api<CapabilityRead>(`/admin/studio/capabilities/${id}/enable`, {
    method: "POST",
    access,
  });
}

async function deleteCapability(access: string, id: number): Promise<void> {
  await api(`/admin/studio/capabilities/${id}`, { method: "DELETE", access, raw: true });
}

function FormFieldEditor({
  fields,
  onChange,
}: {
  fields: FormField[];
  onChange: (fields: FormField[]) => void;
}) {
  const hasSources = fields.some((f) => f.type === "sources");
  const hasLanguage = fields.some((f) => f.type === "language");

  const patchText = (index: number, patch: Partial<TextField>) => {
    onChange(
      fields.map((field, i) => (i === index && field.type === "text" ? { ...field, ...patch } : field)),
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={hasSources}
          onClick={() => onChange([...fields, { type: "sources" }])}
        >
          添加来源
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={hasLanguage}
          onClick={() => onChange([...fields, { type: "language" }])}
        >
          添加语言
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() =>
            onChange([
              ...fields,
              { type: "text", key: "", label: "", placeholder: "", required: false, multiline: false },
            ])
          }
        >
          添加文本
        </Button>
      </div>
      {fields.map((field, index) => (
        <div key={`${field.type}-${index}`} className="admin-inline-form">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium">
              {field.type === "sources" ? "来源" : field.type === "language" ? "语言" : field.type === "select" ? "下拉" : "文本"}
            </span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => onChange(fields.filter((_, i) => i !== index))}
            >
              移除
            </Button>
          </div>
          {field.type === "text" && (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <Input
                placeholder="key"
                value={field.key}
                onChange={(e) => patchText(index, { key: e.target.value })}
                required
                pattern="^[a-z][a-z0-9_]{0,31}$"
              />
              <Input
                placeholder="标题"
                value={field.label}
                onChange={(e) => patchText(index, { label: e.target.value })}
                required
              />
              <Input
                className="md:col-span-2"
                placeholder="提示"
                value={field.placeholder}
                onChange={(e) => patchText(index, { placeholder: e.target.value })}
              />
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={field.required}
                  onChange={(e) => patchText(index, { required: e.target.checked })}
                />
                必填
              </label>
              <select
                className={SELECT_CLASS}
                value={field.multiline ? "multiline" : "single"}
                onChange={(e) => patchText(index, { multiline: e.target.value === "multiline" })}
              >
                <option value="single">单行</option>
                <option value="multiline">多行</option>
              </select>
            </div>
          )}
          {field.type === "select" && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                key=<span className="font-mono">{field.key || "—"}</span>
                {field.default ? ` · 默认 ${field.default}` : ""}
              </p>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {field.options.map((opt) => (
                  <li key={opt.value}>
                    {opt.label} <span className="font-mono text-[10px]">({opt.value})</span>
                  </li>
                ))}
              </ul>
              <p className="text-[11px] text-muted-foreground">预置下拉由代码维护；保存时会原样回写。</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function AdminStudioPanel() {
  const { access } = useAuth();
  const qc = useQueryClient();
  const [form, setForm] = useState<CapabilityFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);

  const formats = useQuery({
    queryKey: ["admin-studio-formats"],
    queryFn: () => listFormats(access ?? ""),
    enabled: !!access,
  });
  const agents = useQuery({
    queryKey: ["admin-agents"],
    queryFn: () => listAgents(access ?? ""),
    enabled: !!access,
  });
  const list = useQuery({
    queryKey: ["admin-studio-capabilities"],
    queryFn: () => listCapabilities(access ?? ""),
    enabled: !!access,
  });

  const save = useMutation({
    mutationFn: () =>
      editingId === null
        ? createCapability(access ?? "", form)
        : updateCapability(access ?? "", editingId, form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-studio-capabilities"] });
      setForm(EMPTY_FORM);
      setEditingId(null);
    },
  });

  const flip = useMutation({
    mutationFn: ({ id, enable }: { id: number; enable: boolean }) =>
      enable ? enableCapability(access ?? "", id) : disableCapability(access ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-studio-capabilities"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteCapability(access ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-studio-capabilities"] }),
  });

  const activeAgents = (agents.data ?? []).filter((a) => a.is_active);
  const assignedAgent = (agents.data ?? []).find((a) => a.id === form.agent_id);
  const agentOptions =
    assignedAgent && !assignedAgent.is_active ? [assignedAgent, ...activeAgents] : activeAgents;

  const formatLabel = (key: string) => formats.data?.find((f) => f.key === key)?.label ?? key;
  const agentName = (id: number | null) => {
    if (id === null) return "—";
    return agents.data?.find((a) => a.id === id)?.name ?? `#${id}`;
  };

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="Studio 能力"
        description="配置产物格式、绑定智能体与用户表单。创建后产物格式不可再改。"
      />

      <AdminSectionCard
        title={editingId === null ? "新建能力" : `编辑能力 #${editingId}`}
        description="表单字段支持来源、语言、文本；预置下拉由代码维护。"
      >
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Input
                  placeholder="名称"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  required
                />
                <Input
                  placeholder="图标（emoji）"
                  value={form.icon}
                  maxLength={16}
                  onChange={(e) => setForm((f) => ({ ...f, icon: e.target.value }))}
                />
                {editingId === null && (
                  <select
                    className={SELECT_CLASS}
                    value={form.format_key}
                    onChange={(e) => setForm((f) => ({ ...f, format_key: e.target.value }))}
                    required
                  >
                    <option value="">产物格式</option>
                    {(formats.data ?? []).map((fmt) => (
                      <option key={fmt.key} value={fmt.key}>
                        {fmt.label}
                      </option>
                    ))}
                  </select>
                )}
                <select
                  className={SELECT_CLASS}
                  value={form.agent_id ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      agent_id: e.target.value === "" ? null : Number(e.target.value),
                    }))
                  }
                >
                  <option value="">不绑定智能体</option>
                  {agentOptions.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                      {agent.is_active ? "" : "（已停用）"}
                    </option>
                  ))}
                </select>
              </div>
              <FormFieldEditor
                fields={form.form}
                onChange={(next) => setForm((f) => ({ ...f, form: next }))}
              />
              <div className="flex gap-2">
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? "保存中…" : editingId === null ? "创建" : "保存"}
                </Button>
                {editingId !== null && (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setEditingId(null);
                      setForm(EMPTY_FORM);
                    }}
                  >
                    取消
                  </Button>
                )}
              </div>
            </form>
            {save.error instanceof ApiError && (
              <p className="mt-2 text-sm text-destructive">{save.error.message}</p>
            )}
      </AdminSectionCard>

        <AdminSectionCard title="能力列表" description={`共 ${list.data?.length ?? "—"} 条`}>
            {list.isLoading && <AdminLoading />}
            {list.error instanceof ApiError && (
              <p className="text-sm text-destructive">{list.error.message}</p>
            )}
            {flip.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{flip.error.message}</p>
            )}
            {remove.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{remove.error.message}</p>
            )}
            {list.data && list.data.length === 0 ? (
              <AdminEmptyState title="暂无能力" description="创建能力后会出现在笔记本右侧 Studio。" />
            ) : null}
            {list.data && list.data.length > 0 ? (
              <AdminTableShell>
                <thead>
                  <tr>
                    <th>图标</th>
                    <th>名称</th>
                    <th>产物格式</th>
                    <th>智能体</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                    {list.data.map((cap) => (
                      <tr key={cap.id}>
                        <td className="text-lg leading-none">{cap.icon ?? "—"}</td>
                        <td className="font-medium">{cap.name}</td>
                        <td className="text-muted-foreground">{formatLabel(cap.format_key)}</td>
                        <td className="text-muted-foreground">{agentName(cap.agent_id)}</td>
                        <td>
                          <AdminStatusBadge tone={cap.enabled ? "ok" : "idle"}>
                            {cap.enabled ? "启用" : "停用"}
                          </AdminStatusBadge>
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingId(cap.id);
                                setForm({
                                  name: cap.name,
                                  icon: cap.icon ?? "",
                                  format_key: cap.format_key,
                                  agent_id: cap.agent_id,
                                  form: parseForm(cap.form_json),
                                });
                              }}
                            >
                              编辑
                            </Button>
                            {cap.enabled ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => flip.mutate({ id: cap.id, enable: false })}
                                disabled={flip.isPending}
                              >
                                停用
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => flip.mutate({ id: cap.id, enable: true })}
                                disabled={flip.isPending}
                              >
                                启用
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={cap.is_builtin || remove.isPending}
                              onClick={() => {
                                if (confirm(`删除能力「${cap.name}」？`)) remove.mutate(cap.id);
                              }}
                            >
                              删除
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
              </AdminTableShell>
            ) : null}
      </AdminSectionCard>
    </div>
  );
}

/** 兼容旧链接 → 后台 Tab */
export default function AdminStudioPage() {
  return <Navigate to="/admin?section=studio&tab=studio" replace />;
}
