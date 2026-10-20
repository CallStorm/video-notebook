import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface SkillRead {
  id: number;
  name: string;
  description: string | null;
}

interface SystemPromptDraft {
  skill_name: string;
  skill_description: string | null;
  system_prompt: string;
}

interface AgentRead {
  id: number;
  name: string;
  provider: string;
  skill_id: number | null;
  system_prompt: string;
  timeout_seconds: number;
  is_active: boolean;
  updated_by: number;
  created_at: string | null;
  updated_at: string | null;
}

interface AgentWrite {
  name: string;
  skill_id: number | null;
  system_prompt: string;
  timeout_seconds: number;
}

const EMPTY_FORM: AgentWrite = {
  name: "",
  skill_id: null,
  system_prompt: "",
  timeout_seconds: 600,
};

const SELECT_CLASS = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const TEXTAREA_CLASS =
  "flex min-h-[96px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

async function listSkills(access: string): Promise<SkillRead[]> {
  return api<SkillRead[]>("/admin/skills", { access });
}

async function listAgents(access: string): Promise<AgentRead[]> {
  return api<AgentRead[]>("/admin/agents", { access });
}

async function saveAgent(access: string, body: AgentWrite, id?: number): Promise<AgentRead> {
  if (id === undefined) {
    return api<AgentRead>("/admin/agents", { method: "POST", body, access });
  }
  return api<AgentRead>(`/admin/agents/${id}`, { method: "PATCH", body, access });
}

async function disableAgent(access: string, id: number): Promise<AgentRead> {
  return api<AgentRead>(`/admin/agents/${id}/disable`, { method: "POST", access });
}

async function enableAgent(access: string, id: number): Promise<AgentRead> {
  return api<AgentRead>(`/admin/agents/${id}/enable`, { method: "POST", access });
}

async function deleteAgent(access: string, id: number): Promise<void> {
  await api(`/admin/agents/${id}`, { method: "DELETE", access, raw: true });
}

async function fetchSystemPromptDraft(
  access: string,
  skillId: number,
  agentName: string,
): Promise<SystemPromptDraft> {
  const params = new URLSearchParams();
  if (agentName.trim()) params.set("agent_name", agentName.trim());
  const qs = params.toString();
  return api<SystemPromptDraft>(
    `/admin/skills/${skillId}/system-prompt-draft${qs ? `?${qs}` : ""}`,
    { access },
  );
}

export function AdminAgentsPanel() {
  const { access } = useAuth();
  const qc = useQueryClient();
  const [form, setForm] = useState<AgentWrite>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [promptHint, setPromptHint] = useState<string | null>(null);

  const skills = useQuery({
    queryKey: ["admin-skills"],
    queryFn: () => listSkills(access ?? ""),
    enabled: !!access,
  });
  const list = useQuery({
    queryKey: ["admin-agents"],
    queryFn: () => listAgents(access ?? ""),
    enabled: !!access,
  });

  const save = useMutation({
    mutationFn: () => saveAgent(access ?? "", form, editingId ?? undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-agents"] });
      setForm(EMPTY_FORM);
      setEditingId(null);
      setPromptHint(null);
    },
  });

  const flip = useMutation({
    mutationFn: ({ id, enable }: { id: number; enable: boolean }) =>
      enable ? enableAgent(access ?? "", id) : disableAgent(access ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-agents"] }),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteAgent(access ?? "", id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-agents"] }),
  });

  const generatePrompt = useMutation({
    mutationFn: () => {
      if (form.skill_id === null) {
        throw new Error("请先选择技能");
      }
      return fetchSystemPromptDraft(access ?? "", form.skill_id, form.name);
    },
    onSuccess: (draft) => {
      setForm((f) => ({ ...f, system_prompt: draft.system_prompt }));
      setPromptHint(`已根据技能「${draft.skill_name}」生成系统提示，可再按需微调。`);
    },
    onError: () => {
      setPromptHint(null);
    },
  });

  const handleGeneratePrompt = () => {
    if (form.skill_id === null) return;
    if (form.system_prompt.trim()) {
      const ok = window.confirm("当前系统提示已有内容，确定用根据技能生成的内容覆盖吗？");
      if (!ok) return;
    }
    setPromptHint(null);
    generatePrompt.mutate();
  };

  const skillName = (skillId: number | null) => {
    if (skillId === null) return "—";
    return skills.data?.find((s) => s.id === skillId)?.name ?? `#${skillId}`;
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">智能体</h2>
        <p className="text-sm text-muted-foreground">
          配置 Claude Code 运行用的技能、提示和超时。模型在「概览」Tab。
        </p>
      </div>

      <Card>
          <CardHeader>
            <CardTitle>{editingId === null ? "新建智能体" : `编辑智能体 #${editingId}`}</CardTitle>
            <CardDescription>
              提供方固定为 claude_code。模型在后台首页的 Claude Code 配置里。超时 30–3600 秒，默认 600。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid grid-cols-1 gap-3 md:grid-cols-2"
              onSubmit={(e) => {
                e.preventDefault();
                save.mutate();
              }}
            >
              <Input
                placeholder="名称"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
              <select
                className={SELECT_CLASS}
                value={form.skill_id ?? ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    skill_id: e.target.value === "" ? null : Number(e.target.value),
                  }))
                }
              >
                <option value="">不绑定</option>
                {(skills.data ?? []).map((skill) => (
                  <option key={skill.id} value={skill.id}>
                    {skill.name}
                  </option>
                ))}
              </select>
              <Input
                type="number"
                min={30}
                max={3600}
                placeholder="超时（秒）"
                value={form.timeout_seconds}
                onChange={(e) =>
                  setForm((f) => ({ ...f, timeout_seconds: Number(e.target.value) }))
                }
                required
              />
              <div className="space-y-2 md:col-span-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="text-sm font-medium" htmlFor="agent-system-prompt">
                    系统提示
                  </label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={form.skill_id === null || generatePrompt.isPending}
                    onClick={handleGeneratePrompt}
                    title={form.skill_id === null ? "请先选择技能" : "根据所选技能生成互补系统提示"}
                  >
                    {generatePrompt.isPending ? "生成中…" : "根据技能生成"}
                  </Button>
                </div>
                <textarea
                  id="agent-system-prompt"
                  className={TEXTAREA_CLASS}
                  placeholder="系统提示（可点「根据技能生成」；运行时技能全文由 .claude/skills 注入，此处写角色与约束即可）"
                  value={form.system_prompt}
                  onChange={(e) => {
                    setPromptHint(null);
                    setForm((f) => ({ ...f, system_prompt: e.target.value }));
                  }}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  运行时会把技能拷到工作区并加载 SKILL.md；系统提示与格式说明、固定约定拼接使用，请勿整份粘贴技能正文。
                </p>
                {promptHint && <p className="text-xs text-emerald-700">{promptHint}</p>}
                {generatePrompt.error instanceof ApiError && (
                  <p className="text-xs text-destructive">{generatePrompt.error.message}</p>
                )}
              </div>
              <div className="flex gap-2 md:col-span-2">
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
                      setPromptHint(null);
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>智能体列表</CardTitle>
            <CardDescription>共 {list.data?.length ?? "—"} 条。</CardDescription>
          </CardHeader>
          <CardContent>
            {list.isLoading && <p className="text-sm text-muted-foreground">加载中…</p>}
            {list.error instanceof ApiError && (
              <p className="text-sm text-destructive">{list.error.message}</p>
            )}
            {flip.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{flip.error.message}</p>
            )}
            {remove.error instanceof ApiError && (
              <p className="mb-3 text-sm text-destructive">{remove.error.message}</p>
            )}
            {list.data && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-2 pr-4">名称</th>
                      <th className="py-2 pr-4">技能名</th>
                      <th className="py-2 pr-4">超时</th>
                      <th className="py-2 pr-4">启用</th>
                      <th className="py-2 pr-4">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.map((agent) => (
                      <tr key={agent.id} className="border-b">
                        <td className="py-2 pr-4">{agent.name}</td>
                        <td className="py-2 pr-4">{skillName(agent.skill_id)}</td>
                        <td className="py-2 pr-4">{agent.timeout_seconds}s</td>
                        <td className="py-2 pr-4">{agent.is_active ? "启用" : "停用"}</td>
                        <td className="py-2 pr-4">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingId(agent.id);
                                setPromptHint(null);
                                setForm({
                                  name: agent.name,
                                  skill_id: agent.skill_id,
                                  system_prompt: agent.system_prompt,
                                  timeout_seconds: agent.timeout_seconds,
                                });
                              }}
                            >
                              编辑
                            </Button>
                            {agent.is_active ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => flip.mutate({ id: agent.id, enable: false })}
                                disabled={flip.isPending}
                              >
                                停用
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => flip.mutate({ id: agent.id, enable: true })}
                                disabled={flip.isPending}
                              >
                                启用
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                if (confirm(`删除智能体「${agent.name}」？`)) remove.mutate(agent.id);
                              }}
                              disabled={remove.isPending}
                            >
                              删除
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
    </div>
  );
}

/** 兼容旧链接 → 后台 Tab */
export default function AdminAgentsPage() {
  return <Navigate to="/admin?tab=agents" replace />;
}
