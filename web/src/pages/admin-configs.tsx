import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Key, Plus, Plug, Trash2, X, Check } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AdminLoading,
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
} from "@/components/admin-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DiscoverModelsDialog } from "@/components/discover-models-dialog";

// ─── types ─────────────────────────────────────────────────────────────
interface ProviderInfo {
  name: string;
  display_name: string;
  modalities: string[];
  default_base_url: string | null;
  test_model: string | null;
  docs_url: string | null;
  anthropic_compat: boolean;
}

interface Credential {
  id: number;
  name: string;
  provider: string;
  modalities: string[];
  base_url: string | null;
  api_key_masked: string;
  has_api_key: boolean;
  is_builtin: boolean;
}

interface ModelRow {
  id: number;
  name: string;
  provider: string;
  type: "language" | "embedding" | "speech_to_text" | "text_to_speech";
  credential_id: number;
}

interface DefaultModelRow {
  role: "chat" | "tts" | "stt" | "logo" | "embedding";
  model_id: number | null;
}

interface TestResult {
  ok: boolean;
  latency_ms: number;
  provider?: string;
  message?: string;
  error?: string;
  response?: string;
}

// ─── fetcher ──────────────────────────────────────────────────────────
async function fetchProviders(): Promise<ProviderInfo[]> {
  return api<ProviderInfo[]>("/providers");
}
async function fetchCredentials(access: string): Promise<Credential[]> {
  return api<Credential[]>("/admin/credentials", { access });
}
async function fetchModels(access: string): Promise<ModelRow[]> {
  return api<ModelRow[]>("/admin/models", { access });
}
async function fetchDefaultModels(access: string): Promise<DefaultModelRow[]> {
  return api<DefaultModelRow[]>("/admin/default-models", { access });
}
async function createCredential(
  access: string,
  body: Record<string, unknown>,
): Promise<Credential> {
  return api<Credential>("/admin/credentials", { method: "POST", body, access });
}
async function deleteCredential(access: string, id: number): Promise<void> {
  await api(`/admin/credentials/${id}`, { method: "DELETE", access, raw: true });
}
async function createModel(
  access: string,
  body: Record<string, unknown>,
): Promise<ModelRow> {
  return api<ModelRow>("/admin/models", { method: "POST", body, access });
}
async function deleteModel(access: string, id: number): Promise<void> {
  await api(`/admin/models/${id}`, { method: "DELETE", access, raw: true });
}
async function setDefaultModel(
  access: string,
  role: string,
  model_id: number,
): Promise<DefaultModelRow> {
  return api<DefaultModelRow>(`/admin/default-models/${role}`, {
    method: "PUT",
    body: { model_id },
    access,
  });
}
async function clearDefaultModel(
  access: string,
  role: string,
): Promise<void> {
  await api(`/admin/default-models/${role}`, { method: "DELETE", access, raw: true });
}
async function testCredentialRequest(
  access: string,
  id: number,
): Promise<TestResult> {
  return api<TestResult>(`/admin/credentials/${id}/test`, {
    method: "POST",
    access,
  });
}
async function testModelRequest(
  access: string,
  id: number,
): Promise<TestResult> {
  return api<TestResult>(`/admin/models/${id}/test`, {
    method: "POST",
    body: {},
    access,
  });
}

// ─── helpers ────────────────────────────────────────────────────────────
const MODALITY_LABEL: Record<string, string> = {
  language: "对话",
  embedding: "向量",
  speech_to_text: "语音转文字",
  text_to_speech: "文字转语音",
};

const MODALITY_COLOR_ACTIVE = "bg-primary/10 text-primary border-primary/20";
const MODALITY_COLOR_INACTIVE = "bg-muted text-muted-foreground border-muted";

function ModalityBadge({ type, active }: { type: string; active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] ${
        active ? MODALITY_COLOR_ACTIVE : MODALITY_COLOR_INACTIVE
      }`}
    >
      {MODALITY_LABEL[type] ?? type}
    </span>
  );
}

const ROLE_MODEL_TYPE: Record<string, "language" | "text_to_speech" | "speech_to_text" | "embedding"> = {
  chat: "language",
  tts: "text_to_speech",
  stt: "speech_to_text",
  logo: "language",
  embedding: "embedding",
};

const ROLE_LABEL: Record<string, string> = {
  chat: "聊天模型",
  tts: "文字转语音",
  stt: "语音转文字",
  logo: "生成图标",
  embedding: "向量模型",
};

// ─── page ─────────────────────────────────────────────────────────────
export function AdminConfigsPage() {
  const { access } = useAuth();
  const token = access ?? "";

  const providers = useQuery({ queryKey: ["providers"], queryFn: fetchProviders });
  const credentials = useQuery({
    queryKey: ["admin-credentials"],
    queryFn: () => fetchCredentials(token),
    enabled: !!token,
  });
  const models = useQuery({
    queryKey: ["admin-models"],
    queryFn: () => fetchModels(token),
    enabled: !!token,
  });
  const defaults = useQuery({
    queryKey: ["admin-default-models"],
    queryFn: () => fetchDefaultModels(token),
    enabled: !!token,
  });

  if (!token) {
    return <NoAccessCard />;
  }
  if (
    providers.isLoading ||
    credentials.isLoading ||
    models.isLoading ||
    defaults.isLoading
  ) {
    return <AdminLoading label="正在加载模型配置…" />;
  }

  const sortedProviders = (providers.data ?? []).slice().sort((a, b) => {
    const aHas = (credentials.data ?? []).some((c) => c.provider === a.name) ? 1 : 0;
    const bHas = (credentials.data ?? []).some((c) => c.provider === b.name) ? 1 : 0;
    return bHas - aHas;
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="模型配置"
        description="先选默认模型，再按服务商管理凭证与命名模型。"
        action={<Key className="h-5 w-5 text-muted-foreground" />}
      />

      {models.data && defaults.data && (
        <DefaultModelSelectors
          token={token}
          models={models.data}
          defaults={defaults.data}
        />
      )}

      {sortedProviders.map((p) => {
        const creds = (credentials.data ?? []).filter((c) => c.provider === p.name);
        const credIds = new Set(creds.map((c) => c.id));
        const providerModels = (models.data ?? []).filter((m) =>
          credIds.has(m.credential_id),
        );
        return (
          <ProviderSection
            key={p.name}
            provider={p}
            credentials={creds}
            models={providerModels}
            allModels={models.data ?? []}
            token={token}
          />
        );
      })}
    </div>
  );
}

function NoAccessCard() {
  return (
    <AdminSectionCard title="登录态丢失" description="请重新登录后再访问本页。">
      <a
        href="/login"
        className="inline-flex rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-glow"
      >
        跳到登录页
      </a>
    </AdminSectionCard>
  );
}

// ─── Default model selectors ─────────────────────────────────────────
function DefaultModelSelectors({
  token,
  models,
  defaults,
}: {
  token: string;
  models: ModelRow[];
  defaults: DefaultModelRow[];
}) {
  const qc = useQueryClient();
  const set = useMutation({
    mutationFn: ({ role, model_id }: { role: string; model_id: number }) =>
      setDefaultModel(token, role, model_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-default-models"] }),
  });
  const clear = useMutation({
    mutationFn: (role: string) => clearDefaultModel(token, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-default-models"] }),
  });

  return (
    <AdminSectionCard
      title="默认模型"
      description="按用途选用模型。对话与向量（语义检索）建议配置；文字转语音 / 语音转文字可留空。"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {defaults.map((row) => {
            const modelType = ROLE_MODEL_TYPE[row.role];
            const available = models.filter((m) => m.type === modelType);
            const current = available.find((m) => m.id === row.model_id);
            return (
              <div key={row.role} className="space-y-1.5">
                <label className="text-xs font-medium">
                  {ROLE_LABEL[row.role] ?? row.role}
                </label>
                <div className="flex gap-1">
                  <select
                    className="admin-select h-9"
                    value={row.model_id ?? ""}
                    onChange={(e) =>
                      set.mutate({ role: row.role, model_id: Number(e.target.value) })
                    }
                    disabled={available.length === 0}
                  >
                    <option value="">— 未选 —</option>
                    {available.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}（{m.provider}）
                      </option>
                    ))}
                  </select>
                  {row.model_id && (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      onClick={() => clear.mutate(row.role)}
                      title="清掉"
                      className="h-9 w-9 shrink-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <p className="text-[10px] text-muted-foreground">
                  {current
                    ? `当前：${current.name}`
                    : available.length === 0
                      ? `还没有 ${modelType} 类型的模型`
                      : "未选"}
                </p>
              </div>
            );
          })}
        </div>
    </AdminSectionCard>
  );
}

// ─── Provider section ────────────────────────────────────────────────
function ProviderSection({
  provider,
  credentials,
  models,
  allModels,
  token,
}: {
  provider: ProviderInfo;
  credentials: Credential[];
  models: ModelRow[];
  allModels: ModelRow[];
  token: string;
}) {
  const hasCreds = credentials.length > 0;
  return (
    <Card className="admin-section-card">
      <CardHeader className="admin-section-header pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <CardTitle className="admin-section-title capitalize">
              {provider.display_name}
            </CardTitle>
            <div className="flex flex-wrap gap-1">
              {provider.modalities.map((m) => (
                <ModalityBadge key={m} type={m} active={hasCreds} />
              ))}
            </div>
          </div>
          {hasCreds ? (
            <AdminStatusBadge tone="ok">
              <Check className="h-3 w-3" /> 已配置
            </AdminStatusBadge>
          ) : (
            <AdminStatusBadge tone="idle">未配置</AdminStatusBadge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {credentials.length === 0 && (
          <p className="text-sm text-muted-foreground">
            还没有凭证。点下方按钮添加。
          </p>
        )}
        {credentials.map((cred) => (
          <CredentialItem
            key={cred.id}
            credential={cred}
            models={models.filter((m) => m.credential_id === cred.id)}
            allModels={allModels}
            token={token}
          />
        ))}
        <AddCredentialButton provider={provider.name} token={token} />
      </CardContent>
    </Card>
  );
}

// ─── Credential item ────────────────────────────────────────────────
function CredentialItem({
  credential,
  models,
  allModels,
  token,
}: {
  credential: Credential;
  models: ModelRow[];
  allModels: ModelRow[];
  token: string;
}) {
  const qc = useQueryClient();
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [editing, setEditing] = useState(false);
  const [showAddModel, setShowAddModel] = useState(false);
  const [showDiscover, setShowDiscover] = useState(false);

  const testCred = useMutation({
    mutationFn: () => testCredentialRequest(token, credential.id),
    onSuccess: (data) => setTestResult(data),
  });
  const testModel = useMutation({
    mutationFn: (modelId: number) => testModelRequest(token, modelId),
    onSuccess: (data) => setTestResult(data),
  });
  const removeCred = useMutation({
    mutationFn: () => deleteCredential(token, credential.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-credentials"] }),
  });
  const removeModel = useMutation({
    mutationFn: (id: number) => deleteModel(token, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-models"] });
      qc.invalidateQueries({ queryKey: ["admin-default-models"] });
    },
  });

  return (
    <div className="admin-inline-form">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{credential.name}</span>
          {credential.modalities.map((m) => (
            <ModalityBadge
              key={m}
              type={m}
              active={models.some((mm) => mm.type === m)}
            />
          ))}
          <span className="font-mono text-[10px] text-muted-foreground">
            {credential.api_key_masked || "无 key"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => testCred.mutate()}
            disabled={testCred.isPending || !credential.has_api_key}
            title="测试连通性"
          >
            <Plug className="h-4 w-4" />
            <span className="ml-1 hidden text-xs sm:inline">测试</span>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setEditing((v) => !v)}
          >
            {editing ? "收起" : "编辑"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive"
            onClick={() => {
              if (confirm(`删除凭证「${credential.name}」？`)) removeCred.mutate();
            }}
            disabled={credential.is_builtin || removeCred.isPending}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {testResult && (
        <div
          className={`rounded-xl border p-2.5 text-xs ${testResult.ok ? "border-[hsl(var(--success))]/30 bg-[hsl(172_50%_94%)]" : "border-destructive/30 bg-destructive/5"}`}
        >
          <div className="text-muted-foreground">
            {testResult.provider ?? "—"} · {testResult.latency_ms} ms
          </div>
          {testResult.ok ? (
            <p className="text-[hsl(var(--success))]">
              {testResult.message ?? testResult.response ?? "OK"}
            </p>
          ) : (
            <p className="text-red-700">{testResult.error}</p>
          )}
        </div>
      )}

      {editing && (
        <EditCredentialForm
          credential={credential}
          token={token}
          onSaved={() => {
            setEditing(false);
            qc.invalidateQueries({ queryKey: ["admin-credentials"] });
          }}
        />
      )}

      {/* Models under this credential */}
      {models.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          {models.map((m) => (
            <div
              key={m.id}
              className="inline-flex items-center gap-1 rounded-md border bg-secondary px-2 py-0.5 font-mono text-[11px]"
            >
              {m.name}
              <span className="text-muted-foreground">({MODALITY_LABEL[m.type]})</span>
              <button
                className="ml-1 text-muted-foreground hover:text-foreground"
                onClick={() => testModel.mutate(m.id)}
                title="测这条模型"
                disabled={testModel.isPending}
              >
                <Plug className="h-3 w-3" />
              </button>
              <button
                className="text-muted-foreground hover:text-destructive"
                onClick={() => {
                  if (confirm(`删除模型「${m.name}」？`)) removeModel.mutate(m.id);
                }}
                title="删"
                disabled={removeModel.isPending}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {showAddModel && (
        <AddModelForm
          credential={credential}
          availableTypes={credential.modalities}
          existingModelNames={allModels
            .filter((m) => m.credential_id === credential.id)
            .map((m) => `${m.name}@${m.type}`)}
          token={token}
          onSaved={() => {
            setShowAddModel(false);
            qc.invalidateQueries({ queryKey: ["admin-models"] });
            qc.invalidateQueries({ queryKey: ["admin-default-models"] });
          }}
          onCancel={() => setShowAddModel(false)}
        />
      )}

      {!showAddModel && !editing && (
        <div className="flex flex-col gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setShowDiscover(true)}
            className="w-full text-xs"
            disabled={!credential.has_api_key}
            title={credential.has_api_key ? "从服务商拉取模型列表" : "先设置 API Key"}
          >
            <Plug className="h-3 w-3" />
            <span className="ml-1">发现模型（从服务商拉取）</span>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setShowAddModel(true)}
            className="w-full text-xs"
          >
            <Plus className="h-3 w-3" />
            <span className="ml-1">手动添加模型名</span>
          </Button>
        </div>
      )}

      {showDiscover && (
        <DiscoverModelsDialog
          open={showDiscover}
          onOpenChange={setShowDiscover}
          credentialId={credential.id}
          credentialName={credential.name}
          availableTypes={credential.modalities}
          existing={models.map((m) => `${m.name}@${m.type}`)}
          token={token}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin-models"] });
            qc.invalidateQueries({ queryKey: ["admin-default-models"] });
          }}
        />
      )}
    </div>
  );
}

// ─── Add credential form (inline) ────────────────────────────────────
function AddCredentialButton({
  provider,
  token,
}: {
  provider: string;
  token: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <AddCredentialForm
        provider={provider}
        token={token}
        onSaved={() => {
          setOpen(false);
          qc.invalidateQueries({ queryKey: ["admin-credentials"] });
        }}
        onCancel={() => setOpen(false)}
      />
    );
  }
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      onClick={() => setOpen(true)}
      className="w-full"
    >
      <Plus className="h-4 w-4" />
      <span className="ml-1">添加凭证</span>
    </Button>
  );
}

function AddCredentialForm({
  provider,
  token,
  onSaved,
  onCancel,
}: {
  provider: string;
  token: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const providers = useQuery({ queryKey: ["providers"], queryFn: fetchProviders });
  const spec = providers.data?.find((p) => p.name === provider);
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modalities, setModalities] = useState<string[]>(spec?.modalities ?? []);

  const create = useMutation({
    mutationFn: () =>
      createCredential(token, {
        name: name.trim(),
        provider,
        api_key: apiKey,
        base_url: baseUrl || null,
        modalities,
      }),
    onSuccess: onSaved,
  });

  return (
    <form
      className="admin-inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name && apiKey) create.mutate();
      }}
    >
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        <Input
          placeholder="凭证名（标识）"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <Input
          type="password"
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          required
        />
        <Input
          className="md:col-span-2"
          placeholder={spec?.default_base_url ?? "Base URL（留空用 provider 默认）"}
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">能力类型：</span>
        {(spec?.modalities ?? []).map((m) => (
          <label key={m} className="inline-flex items-center gap-1">
            <input
              type="checkbox"
              checked={modalities.includes(m)}
              onChange={(e) =>
                setModalities(
                  e.target.checked
                    ? [...modalities, m]
                    : modalities.filter((x) => x !== m),
                )
              }
            />
            {MODALITY_LABEL[m] ?? m}
          </label>
        ))}
      </div>
      {spec?.docs_url && (
        <a
          href={spec.docs_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 underline"
        >
          获取 API Key ↗
        </a>
      )}
      {create.error instanceof ApiError && (
        <p className="text-sm text-destructive">
          {create.error.code}: {create.error.message}
        </p>
      )}
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={create.isPending}>
          {create.isPending ? "保存中…" : "保存"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          取消
        </Button>
      </div>
    </form>
  );
}

function EditCredentialForm({
  credential,
  token,
  onSaved,
}: {
  credential: Credential;
  token: string;
  onSaved: () => void;
}) {
  const [name, setName] = useState(credential.name);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(credential.base_url ?? "");

  const save = useMutation({
    mutationFn: () =>
      api(`/admin/credentials/${credential.id}`, {
        method: "PATCH",
        body: {
          name: name.trim(),
          api_key: apiKey || undefined,
          base_url: baseUrl || null,
        },
        access: token,
      }),
    onSuccess: onSaved,
  });

  return (
    <form
      className="admin-inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
        <Input
          type="password"
          placeholder="API Key（留空 = 不改）"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <Input
          className="md:col-span-2"
          placeholder="Base URL"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />
      </div>
      {save.error instanceof ApiError && (
        <p className="text-sm text-destructive">
          {save.error.code}: {save.error.message}
        </p>
      )}
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" disabled={save.isPending}>
          {save.isPending ? "保存中…" : "保存"}
        </Button>
      </div>
    </form>
  );
}

// ─── Add model form (inline) ────────────────────────────────────────
function AddModelForm({
  credential,
  availableTypes,
  existingModelNames,
  token,
  onSaved,
  onCancel,
}: {
  credential: Credential;
  availableTypes: string[];
  existingModelNames: string[];
  token: string;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<string>(availableTypes[0] ?? "language");
  const create = useMutation({
    mutationFn: () =>
      createModel(token, {
        name: name.trim(),
        provider: credential.provider,
        type,
        credential_id: credential.id,
      }),
    onSuccess: onSaved,
  });

  const dup = existingModelNames.includes(`${name.trim()}@${type}`);

  return (
    <form
      className="admin-inline-form flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (name && !dup) create.mutate();
      }}
    >
      <Input
        placeholder="模型名（如 MiniMax-M3）"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        className="max-w-[180px]"
      />
      <select
        className="admin-select h-9 w-auto"
        value={type}
        onChange={(e) => setType(e.target.value)}
      >
        {availableTypes.map((t) => (
          <option key={t} value={t}>
            {MODALITY_LABEL[t] ?? t}
          </option>
        ))}
      </select>
      {dup && <span className="text-xs text-destructive">该名 + 类型已存在</span>}
      {create.error instanceof ApiError && (
        <span className="text-xs text-destructive">
          {create.error.code}: {create.error.message}
        </span>
      )}
      <Button type="submit" size="sm" disabled={create.isPending || dup}>
        {create.isPending ? "保存中…" : "保存"}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
        取消
      </Button>
    </form>
  );
}
