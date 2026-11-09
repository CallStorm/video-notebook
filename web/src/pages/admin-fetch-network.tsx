import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Globe, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AdminPageHeader,
  AdminSectionCard,
  AdminStatusBadge,
} from "@/components/admin-shell";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Platform = "youtube" | "bilibili";
type ProxyScheme = "http" | "https" | "socks5" | "socks4";

interface PlatformCookieRead {
  platform: Platform;
  enabled: boolean;
  cookie_set: boolean;
  updated_at: string | null;
}

interface ProxyRead {
  enabled: boolean;
  proxy_set: boolean;
  apply_to: Platform[];
  scheme: ProxyScheme | null;
  host: string | null;
  port: number | null;
}

interface DouyinParserRead {
  base_url: string;
  api_key_set: boolean;
  host_rules: string[];
}

interface FetchNetworkRead {
  cookies: PlatformCookieRead[];
  proxy: ProxyRead;
  douyin_parser: DouyinParserRead;
}

interface ProxyTestResult {
  ok: boolean;
  message: string;
  latency_ms: number | null;
}

const PLATFORM_LABEL: Record<Platform, string> = {
  youtube: "YouTube",
  bilibili: "B站",
};

const PLATFORMS: Platform[] = ["youtube", "bilibili"];
const SCHEMES: ProxyScheme[] = ["http", "https", "socks5", "socks4"];
const DEFAULT_DOUYIN_RULES = ["v.douyin.com", "douyin.com", "iesdouyin.com"];

function hostOf(raw: string): string {
  const text = raw.trim().toLowerCase();
  if (!text) return "";
  try {
    const withScheme = text.includes("://") ? text : `https://${text}`;
    return new URL(withScheme).hostname.replace(/\.$/, "");
  } catch {
    return "";
  }
}

function matchedRule(rawUrl: string, rules: string[]): string | null {
  const host = hostOf(rawUrl);
  if (!host) return null;
  const hits = rules.filter((rule) => host === rule || host.endsWith(`.${rule}`));
  if (!hits.length) return null;
  return hits.sort((a, b) => b.length - a.length)[0];
}

export function AdminFetchNetworkPage() {
  const { access } = useAuth();
  const token = access ?? "";
  const qc = useQueryClient();
  const fileRefs = useRef<Partial<Record<Platform, HTMLInputElement | null>>>({});

  const config = useQuery({
    queryKey: ["admin-fetch-network"],
    queryFn: () => api<FetchNetworkRead>("/admin/fetch-network", { access: token }),
    enabled: !!token,
  });

  const [manualOpen, setManualOpen] = useState<Platform | null>(null);
  const [draftEnabled, setDraftEnabled] = useState<Record<Platform, boolean>>({
    youtube: true,
    bilibili: true,
  });
  const [draftText, setDraftText] = useState<Record<Platform, string>>({
    youtube: "",
    bilibili: "",
  });

  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [scheme, setScheme] = useState<ProxyScheme>("http");
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("7890");
  const [applyTo, setApplyTo] = useState<Platform[]>(["youtube"]);
  const [testResult, setTestResult] = useState<ProxyTestResult | null>(null);
  const [douyinBase, setDouyinBase] = useState("http://127.0.0.1:8001");
  const [douyinKey, setDouyinKey] = useState("");
  const [douyinRules, setDouyinRules] = useState<string[]>(DEFAULT_DOUYIN_RULES);
  const [ruleDraft, setRuleDraft] = useState("");
  const [probe, setProbe] = useState("https://v.douyin.com/tIqoVziKWl8/");
  const [douyinTest, setDouyinTest] = useState<ProxyTestResult | null>(null);

  useEffect(() => {
    if (!config.data) return;
    const nextEnabled: Record<Platform, boolean> = {
      youtube: false,
      bilibili: false,
    };
    for (const c of config.data.cookies) {
      nextEnabled[c.platform] = c.enabled;
    }
    setDraftEnabled(nextEnabled);
    setProxyEnabled(config.data.proxy.enabled);
    setApplyTo(config.data.proxy.apply_to.length ? config.data.proxy.apply_to : ["youtube"]);
    if (config.data.proxy.scheme) setScheme(config.data.proxy.scheme);
    if (config.data.proxy.host) setHost(config.data.proxy.host);
    if (config.data.proxy.port) setPort(String(config.data.proxy.port));
    setDouyinBase(config.data.douyin_parser.base_url || "http://127.0.0.1:8001");
    setDouyinRules(
      config.data.douyin_parser.host_rules.length
        ? config.data.douyin_parser.host_rules
        : [],
    );
  }, [config.data]);

  const saveCookie = useMutation({
    mutationFn: ({
      platform,
      cookie_text,
      enabled,
    }: {
      platform: Platform;
      cookie_text: string | null;
      enabled: boolean;
    }) =>
      api<FetchNetworkRead>(`/admin/fetch-network/cookies/${platform}`, {
        method: "PUT",
        access: token,
        body: { enabled, cookie_text },
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["admin-fetch-network"] });
      setDraftText((prev) => ({ ...prev, [vars.platform]: "" }));
      setManualOpen(null);
    },
  });

  const clearCookie = useMutation({
    mutationFn: (platform: Platform) =>
      api<FetchNetworkRead>(`/admin/fetch-network/cookies/${platform}`, {
        method: "DELETE",
        access: token,
      }),
    onSuccess: (_data, platform) => {
      qc.invalidateQueries({ queryKey: ["admin-fetch-network"] });
      setDraftText((prev) => ({ ...prev, [platform]: "" }));
      setManualOpen(null);
    },
  });

  const saveProxy = useMutation({
    mutationFn: () =>
      api<FetchNetworkRead>("/admin/fetch-network/proxy", {
        method: "PUT",
        access: token,
        body: {
          enabled: proxyEnabled,
          apply_to: applyTo,
          scheme,
          host: host.trim(),
          port: Number(port),
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-fetch-network"] });
      setTestResult(null);
    },
  });

  const clearProxy = useMutation({
    mutationFn: () =>
      api<FetchNetworkRead>("/admin/fetch-network/proxy", {
        method: "DELETE",
        access: token,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-fetch-network"] });
      setProxyEnabled(false);
      setTestResult(null);
    },
  });

  const testProxy = useMutation({
    mutationFn: () =>
      api<ProxyTestResult>("/admin/fetch-network/proxy/test", {
        method: "POST",
        access: token,
      }),
    onSuccess: (data) => setTestResult(data),
  });

  const saveDouyin = useMutation({
    mutationFn: () =>
      api<FetchNetworkRead>("/admin/fetch-network/douyin-parser", {
        method: "PUT",
        access: token,
        body: {
          base_url: douyinBase.trim(),
          api_key: douyinKey.trim() ? douyinKey.trim() : null,
          host_rules: douyinRules,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-fetch-network"] });
      setDouyinKey("");
      setDouyinTest(null);
    },
  });

  const testDouyin = useMutation({
    mutationFn: () =>
      api<ProxyTestResult>("/admin/fetch-network/douyin-parser/test", {
        method: "POST",
        access: token,
      }),
    onSuccess: (data) => setDouyinTest(data),
  });

  function addRule() {
    const host = hostOf(ruleDraft);
    if (!host || douyinRules.includes(host)) {
      setRuleDraft("");
      return;
    }
    setDouyinRules((prev) => [...prev, host]);
    setRuleDraft("");
  }

  function toggleApply(platform: Platform) {
    setApplyTo((prev) =>
      prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform],
    );
  }

  function onUploadFile(platform: Platform, file: File | null) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      saveCookie.mutate({
        platform,
        cookie_text: text,
        enabled: true,
      });
    };
    reader.readAsText(file);
  }

  const cookieByPlatform = Object.fromEntries(
    (config.data?.cookies ?? []).map((c) => [c.platform, c]),
  ) as Partial<Record<Platform, PlatformCookieRead>>;

  return (
    <div className="space-y-5">
      <AdminPageHeader
        title="抓取与网络"
        description="按平台配置 Cookie 与代理，并指定哪些域名走抖音解析。"
      />

      <AdminSectionCard
        title="平台 Cookie"
        description="上传或粘贴 Netscape Cookie。启用后才会用于抓取与搜索。"
      >

        {config.error instanceof ApiError && (
          <p className="text-sm text-destructive">{config.error.message}</p>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {PLATFORMS.map((platform) => {
            const meta = cookieByPlatform[platform];
            const open = manualOpen === platform;
            return (
              <div
                key={platform}
                className="admin-tile"
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold">{PLATFORM_LABEL[platform]}</h3>
                  {meta?.cookie_set ? (
                    <AdminStatusBadge tone="ok">
                      <Check className="h-3 w-3" />
                      已配置
                    </AdminStatusBadge>
                  ) : (
                    <AdminStatusBadge tone="idle">未配置</AdminStatusBadge>
                  )}
                  {meta?.cookie_set ? (
                    meta.enabled ? (
                      <AdminStatusBadge tone="info">已启用</AdminStatusBadge>
                    ) : (
                      <AdminStatusBadge tone="warn">未启用</AdminStatusBadge>
                    )
                  ) : null}
                </div>

                <label className="mb-3 flex items-start gap-2.5 rounded-xl border border-border/50 bg-background/60 px-3 py-2.5">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={Boolean(meta?.enabled)}
                    disabled={!meta?.cookie_set || saveCookie.isPending}
                    onChange={(e) => {
                      if (!meta?.cookie_set) return;
                      saveCookie.mutate({
                        platform,
                        cookie_text: null,
                        enabled: e.target.checked,
                      });
                    }}
                  />
                  <span>
                    <span className="block text-sm font-medium">启用 Cookie</span>
                    <span className="text-xs text-muted-foreground">
                      {meta?.cookie_set
                        ? "关闭后抓取/搜索不会使用该平台 Cookie"
                        : "请先上传或手动粘贴 Cookie"}
                    </span>
                  </span>
                </label>

                <div className="flex flex-wrap gap-2">
                  <input
                    ref={(el) => {
                      fileRefs.current[platform] = el;
                    }}
                    type="file"
                    accept=".txt,text/plain"
                    className="hidden"
                    onChange={(e) => {
                      onUploadFile(platform, e.target.files?.[0] ?? null);
                      e.target.value = "";
                    }}
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="rounded-lg bg-amber-700 text-white hover:bg-amber-700/90"
                    disabled={saveCookie.isPending}
                    onClick={() => fileRefs.current[platform]?.click()}
                  >
                    <Upload className="h-3.5 w-3.5" />
                    上传
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    className="rounded-lg"
                    onClick={() =>
                      setManualOpen((cur) => (cur === platform ? null : platform))
                    }
                  >
                    手动设置
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="rounded-lg border-destructive/40 text-destructive hover:bg-destructive/10"
                    disabled={clearCookie.isPending || !meta?.cookie_set}
                    onClick={() => {
                      if (confirm(`删除 ${PLATFORM_LABEL[platform]} Cookie？`)) {
                        clearCookie.mutate(platform);
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    删除
                  </Button>
                </div>

                {open && (
                  <div className="mt-4 space-y-3 border-t border-border/50 pt-4">
                    <p className="text-xs text-muted-foreground">粘贴 Netscape cookie 正文后保存（会同时按上方开关决定是否启用）。</p>
                    <textarea
                      className="min-h-[120px] w-full rounded-xl border border-input bg-background px-3 py-2 text-xs font-mono"
                      placeholder="粘贴 Netscape cookie，或 name=value; …"
                      value={draftText[platform]}
                      onChange={(e) =>
                        setDraftText((prev) => ({ ...prev, [platform]: e.target.value }))
                      }
                    />
                    <Button
                      type="button"
                      size="sm"
                      className="rounded-full"
                      disabled={saveCookie.isPending || !draftText[platform].trim()}
                      onClick={() =>
                        saveCookie.mutate({
                          platform,
                          cookie_text: draftText[platform],
                          enabled: Boolean(meta?.enabled) || draftEnabled[platform],
                        })
                      }
                    >
                      保存
                    </Button>
                    {saveCookie.isError && saveCookie.variables?.platform === platform && (
                      <p className="text-sm text-destructive">
                        {saveCookie.error instanceof ApiError
                          ? saveCookie.error.message
                          : "保存失败"}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </AdminSectionCard>

      <AdminSectionCard
        title="抖音解析"
        description="命中下面域名的链接交给本机解析服务。Key 只保存在服务器上。"
        action={
          config.data?.douyin_parser.api_key_set ? (
            <AdminStatusBadge tone="ok">已配置</AdminStatusBadge>
          ) : (
            <AdminStatusBadge tone="idle">未配置</AdminStatusBadge>
          )
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="douyin-base">
              服务地址
            </label>
            <Input
              id="douyin-base"
              value={douyinBase}
              onChange={(e) => setDouyinBase(e.target.value)}
              placeholder="http://127.0.0.1:8001"
              autoComplete="off"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="douyin-key">
              API Key
            </label>
            <Input
              id="douyin-key"
              type="password"
              value={douyinKey}
              onChange={(e) => setDouyinKey(e.target.value)}
              placeholder={
                config.data?.douyin_parser.api_key_set
                  ? "已保存，留空则不修改"
                  : "粘贴 douyin:read 的 Key"
              }
              autoComplete="off"
            />
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">哪些链接走这里</p>
          <p className="text-xs text-muted-foreground">
            按域名匹配。命中域名本身或其子域名就走抖音解析。点域名可删除。
          </p>
          <div className="flex flex-wrap gap-2">
            {douyinRules.map((rule) => (
              <button
                key={rule}
                type="button"
                className="rounded-full bg-muted px-3 py-1 text-sm"
                onClick={() => setDouyinRules((prev) => prev.filter((item) => item !== rule))}
              >
                {rule} ×
              </button>
            ))}
            {douyinRules.length === 0 && (
              <span className="text-xs text-muted-foreground">规则是空的，抖音链接不会走解析服务。</span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Input
              value={ruleDraft}
              onChange={(e) => setRuleDraft(e.target.value)}
              placeholder="例如 m.douyin.com"
              className="max-w-xs"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addRule();
                }
              }}
            />
            <Button type="button" size="sm" variant="secondary" className="rounded-lg" onClick={addRule}>
              添加
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="douyin-probe">
            用一条链接试匹配
          </label>
          <Input
            id="douyin-probe"
            value={probe}
            onChange={(e) => setProbe(e.target.value)}
            placeholder="https://v.douyin.com/..."
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            {matchedRule(probe, douyinRules)
              ? `会走抖音解析，命中 ${matchedRule(probe, douyinRules)}`
              : "不会走抖音解析"}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            className="rounded-lg"
            disabled={saveDouyin.isPending || !douyinBase.trim()}
            onClick={() => saveDouyin.mutate()}
          >
            <Check className="h-4 w-4" />
            {saveDouyin.isPending ? "保存中…" : "保存"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-lg"
            disabled={testDouyin.isPending || !config.data?.douyin_parser.api_key_set}
            onClick={() => testDouyin.mutate()}
          >
            {testDouyin.isPending ? "测试中…" : "测试连接"}
          </Button>
        </div>
        {saveDouyin.error instanceof ApiError && (
          <p className="text-sm text-destructive">{saveDouyin.error.message}</p>
        )}
        {douyinTest && (
          <p className={`text-sm ${douyinTest.ok ? "text-[hsl(var(--success))]" : "text-destructive"}`}>
            {douyinTest.message}
            {douyinTest.latency_ms != null ? `（${douyinTest.latency_ms} ms）` : ""}
          </p>
        )}
      </AdminSectionCard>

      <AdminSectionCard
        title="代理设置"
        description="用于访问 YouTube 等境外平台；可按平台选择是否走代理。"
        action={<Globe className="h-5 w-5 text-muted-foreground" />}
      >

        <div className="space-y-3 rounded-xl border border-border/50 bg-muted/15 p-3.5">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1"
              checked={proxyEnabled}
              onChange={(e) => setProxyEnabled(e.target.checked)}
            />
            <span>
              <span className="block text-sm font-medium">启用代理</span>
              <span className="text-xs text-muted-foreground">
                启用后，勾选平台的抓取与搜索请求将通过代理转发
              </span>
            </span>
          </label>
        </div>

        <div className="space-y-3 rounded-xl border border-border/50 bg-muted/15 p-3.5">
          <p className="text-sm font-medium">代理类型</p>
          <div className="flex flex-wrap gap-2">
            {SCHEMES.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setScheme(item)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium uppercase transition ${scheme === item ? "bg-primary text-primary-foreground shadow-glow" : "bg-muted text-muted-foreground hover:text-foreground"}`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 rounded-xl border border-border/50 bg-muted/15 p-3.5 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="proxy-host">
              代理地址
            </label>
            <Input
              id="proxy-host"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="127.0.0.1"
              autoComplete="off"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="proxy-port">
              端口
            </label>
            <Input
              id="proxy-port"
              value={port}
              onChange={(e) => setPort(e.target.value.replace(/[^\d]/g, ""))}
              placeholder="7890"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="space-y-3 rounded-xl border border-border/50 bg-muted/15 p-3.5">
          <p className="text-sm font-medium">应用到</p>
          <div className="flex flex-wrap gap-4 text-sm">
            {PLATFORMS.map((platform) => (
              <label key={platform} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={applyTo.includes(platform)}
                  onChange={() => toggleApply(platform)}
                />
                {PLATFORM_LABEL[platform]}
              </label>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            className="rounded-lg"
            disabled={saveProxy.isPending || !host.trim() || !port}
            onClick={() => saveProxy.mutate()}
          >
            <Check className="h-4 w-4" />
            {saveProxy.isPending ? "保存中…" : "保存配置"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-lg border-emerald-600/40 text-emerald-700 hover:bg-emerald-500/10"
            disabled={testProxy.isPending || !config.data?.proxy.proxy_set}
            onClick={() => testProxy.mutate()}
          >
            {testProxy.isPending ? "测试中…" : "测试代理"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="rounded-lg border-destructive/40 text-destructive hover:bg-destructive/10"
            disabled={clearProxy.isPending || !config.data?.proxy.proxy_set}
            onClick={() => {
              if (confirm("清除代理配置？")) clearProxy.mutate();
            }}
          >
            <Trash2 className="h-4 w-4" />
            清除代理
          </Button>
        </div>

        {saveProxy.error instanceof ApiError && (
          <p className="text-sm text-destructive">{saveProxy.error.message}</p>
        )}
        {testResult && (
          <p className={`text-sm ${testResult.ok ? "text-[hsl(var(--success))]" : "text-destructive"}`}>
            {testResult.message}
            {testResult.latency_ms != null ? `（${testResult.latency_ms} ms）` : ""}
          </p>
        )}
      </AdminSectionCard>
    </div>
  );
}
