import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useMemo } from "react";
import {
  Activity,
  ArrowLeft,
  Cable,
  Home,
  LogOut,
  Settings2,
  Users,
} from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { UserMenu } from "@/components/user-menu";
import { useAuth } from "@/lib/auth";
import { AdminClaudePage } from "@/pages/admin-claude";
import { AdminUsersPage } from "@/pages/admin-users";
import { AdminPipelineLogsPage } from "@/pages/admin-pipeline-logs";
import { AdminLlmTracesPage } from "@/pages/admin-llm-traces";
import { AdminSettingsPage } from "@/pages/admin-settings";
import { AdminConfigsPage } from "@/pages/admin-configs";
import { AdminFetchNetworkPage } from "@/pages/admin-fetch-network";
import { AdminFetchSettingsPage } from "@/pages/admin-fetch-settings";
import { AdminSubtitleSlicePage } from "@/pages/admin-subtitle-slice";
import { AdminOverviewPage } from "@/pages/admin-overview";
import { AdminCoverPage } from "@/pages/admin-cover";
import { AdminChatPage } from "@/pages/admin-chat";
import { AdminVectorPage } from "@/pages/admin-vector";
import { AdminDraftStrategiesPanel } from "@/pages/admin-draft-strategies";
import { AdminDashboard } from "@/pages/admin-dashboard";
import { cn } from "@/lib/utils";

type AdminSection = "pipeline" | "observability" | "settings" | "accounts";

type PipelineStep =
  | "models"
  | "fetch-network"
  | "fetch-settings"
  | "subtitle-slice"
  | "source-overview"
  | "draft"
  | "cover"
  | "vector"
  | "chat";

type ObservabilityTab = "pipeline-logs" | "llm-traces";

const PIPELINE_STEPS: { id: PipelineStep; label: string; hint: string }[] = [
  { id: "models", label: "模型", hint: "模型与 Claude Code" },
  { id: "fetch-network", label: "网络", hint: "Cookie 与代理" },
  { id: "fetch-settings", label: "抓取", hint: "并发与分块" },
  { id: "subtitle-slice", label: "切片", hint: "ASR 切段" },
  { id: "source-overview", label: "概览", hint: "自动概览与提示词" },
  { id: "draft", label: "底稿", hint: "策略与输出上限" },
  { id: "cover", label: "封面", hint: "文生图" },
  { id: "vector", label: "向量", hint: "语义索引" },
  { id: "chat", label: "对话", hint: "历史轮数" },
];

const OBS_TABS: { id: ObservabilityTab; label: string }[] = [
  { id: "pipeline-logs", label: "流水线日志" },
  { id: "llm-traces", label: "LLM 调用" },
];

const SIDE_NAV: {
  id: "home" | AdminSection;
  label: string;
  icon: typeof Home;
}[] = [
  { id: "home", label: "首页", icon: Home },
  { id: "pipeline", label: "内容流水线", icon: Cable },
  { id: "observability", label: "运行观测", icon: Activity },
  { id: "settings", label: "系统设置", icon: Settings2 },
  { id: "accounts", label: "账号管理", icon: Users },
];

/** 旧 ?tab= 映射到 section + step/tab */
const OLD_TAB_MAP: Record<
  string,
  { section: AdminSection; step?: PipelineStep; tab?: ObservabilityTab }
> = {
  overview: { section: "pipeline", step: "models" },
  models: { section: "pipeline", step: "models" },
  "fetch-network": { section: "pipeline", step: "fetch-network" },
  "fetch-settings": { section: "pipeline", step: "fetch-settings" },
  "subtitle-slice": { section: "pipeline", step: "subtitle-slice" },
  "source-overview": { section: "pipeline", step: "source-overview" },
  draft: { section: "pipeline", step: "draft" },
  "draft-strategies": { section: "pipeline", step: "draft" },
  cover: { section: "pipeline", step: "cover" },
  vector: { section: "pipeline", step: "vector" },
  chat: { section: "pipeline", step: "chat" },
  accounts: { section: "accounts" },
  "pipeline-logs": { section: "observability", tab: "pipeline-logs" },
  "llm-traces": { section: "observability", tab: "llm-traces" },
  settings: { section: "settings" },
};

function isSection(v: string | null): v is AdminSection {
  return (
    v === "pipeline" ||
    v === "observability" ||
    v === "settings" ||
    v === "accounts"
  );
}

function isPipelineStep(v: string | null): v is PipelineStep {
  return PIPELINE_STEPS.some((s) => s.id === v);
}

function isObsTab(v: string | null): v is ObservabilityTab {
  return v === "pipeline-logs" || v === "llm-traces";
}

function paramsFor(
  section: AdminSection,
  opts?: { step?: PipelineStep; tab?: ObservabilityTab },
): Record<string, string> {
  if (section === "pipeline") {
    return { section, step: opts?.step ?? "models" };
  }
  if (section === "observability") {
    return { section, tab: opts?.tab ?? "pipeline-logs" };
  }
  return { section };
}

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // 兼容旧书签：?tab=xxx、section=observability|system|draft-strategies|pipeline-logs|llm-traces
  useEffect(() => {
    const oldTab = searchParams.get("tab");
    const sectionNow = searchParams.get("section");
    const stepNow = searchParams.get("step");

    // Studio 能力后台已移除：旧链接回到后台首页
    if (
      sectionNow === "studio" ||
      oldTab === "studio" ||
      oldTab === "skills" ||
      oldTab === "agents"
    ) {
      setSearchParams({}, { replace: true });
      return;
    }

    // 独立「底稿策略」→ 内容流水线 · 底稿
    if (sectionNow === "draft-strategies") {
      setSearchParams(paramsFor("pipeline", { step: "draft" }), { replace: true });
      return;
    }

    // 独立日志 / LLM 追踪 → 运行观测对应 Tab
    if (sectionNow === "pipeline-logs" || sectionNow === "llm-traces") {
      setSearchParams(paramsFor("observability", { tab: sectionNow }), {
        replace: true,
      });
      return;
    }

    if (sectionNow === "system") {
      if (oldTab === "pipeline-logs" || oldTab === "llm-traces") {
        setSearchParams(paramsFor("observability", { tab: oldTab }), {
          replace: true,
        });
        return;
      }
      if (oldTab === "settings") {
        setSearchParams(paramsFor("settings"), { replace: true });
        return;
      }
      setSearchParams(paramsFor("accounts"), { replace: true });
      return;
    }

    if (sectionNow === "observability") {
      // tab 即观测子页；缺失或不合法时补默认
      if (!isObsTab(searchParams.get("tab"))) {
        setSearchParams(paramsFor("observability", { tab: "pipeline-logs" }), {
          replace: true,
        });
      }
      return;
    }

    // 旧 step=draft-strategies
    if (sectionNow === "pipeline" && stepNow === "draft-strategies") {
      setSearchParams(paramsFor("pipeline", { step: "draft" }), { replace: true });
      return;
    }

    const hasSection = isSection(sectionNow);
    if (!oldTab || hasSection) return;
    const mapped = OLD_TAB_MAP[oldTab];
    if (!mapped) return;
    setSearchParams(
      paramsFor(mapped.section, { step: mapped.step, tab: mapped.tab }),
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  const sectionRaw = searchParams.get("section");
  // 渲染期兼容：旧 section 在 URL 改写前仍能落到正确面板
  const legacySection =
    sectionRaw === "draft-strategies"
      ? ("pipeline" as const)
      : sectionRaw === "pipeline-logs" || sectionRaw === "llm-traces"
        ? ("observability" as const)
        : null;
  const section: AdminSection | null = isSection(sectionRaw)
    ? sectionRaw
    : legacySection;
  const sideActive: "home" | AdminSection = section ?? "home";

  const stepRaw = searchParams.get("step");
  const pipelineStep: PipelineStep =
    sectionRaw === "draft-strategies" || stepRaw === "draft-strategies"
      ? "draft"
      : isPipelineStep(stepRaw)
        ? stepRaw
        : "models";

  const tabRaw = searchParams.get("tab");
  const obsTab: ObservabilityTab =
    sectionRaw === "pipeline-logs" || sectionRaw === "llm-traces"
      ? sectionRaw
      : isObsTab(tabRaw)
        ? tabRaw
        : "pipeline-logs";

  const stepIndex = useMemo(
    () => PIPELINE_STEPS.findIndex((s) => s.id === pipelineStep),
    [pipelineStep],
  );

  function goHub() {
    setSearchParams({}, { replace: true });
  }

  function goSection(next: AdminSection) {
    setSearchParams(paramsFor(next), { replace: true });
  }

  function goPipelineStep(step: PipelineStep) {
    setSearchParams(paramsFor("pipeline", { step }), { replace: true });
  }

  function goObsTab(tab: ObservabilityTab) {
    setSearchParams(paramsFor("observability", { tab }), { replace: true });
  }

  function goPrevStep() {
    if (stepIndex <= 0) return;
    goPipelineStep(PIPELINE_STEPS[stepIndex - 1].id);
  }

  function goNextStep() {
    if (stepIndex < 0 || stepIndex >= PIPELINE_STEPS.length - 1) return;
    goPipelineStep(PIPELINE_STEPS[stepIndex + 1].id);
  }

  function onSideNav(id: "home" | AdminSection) {
    if (id === "home") goHub();
    else goSection(id);
  }

  return (
    <div className="page-ambient flex min-h-screen flex-col">
      <AppHeader
        active="admin"
        sticky={false}
        rightSlot={
          <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
            <span className="hidden sm:inline max-w-[10rem] truncate">{user?.name}</span>
            <Link
              to="/"
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-muted-foreground transition hover:bg-accent/60 hover:text-primary"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回前台
            </Link>
            <UserMenu
              onLogout={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            />
          </div>
        }
      />

      <div className="admin-shell">
        <aside className="admin-side" aria-label="管理配置导航">
          <nav className="admin-side-nav">
            {SIDE_NAV.map((item) => {
              const Icon = item.icon;
              const active = sideActive === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSideNav(item.id)}
                  className={cn("admin-side-item", active && "admin-side-item-active")}
                >
                  <Icon className="h-4 w-4 shrink-0 opacity-80" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <div className="admin-side-footer">
            <div className="admin-side-status">
              <span className="admin-side-status-dot" aria-hidden />
              系统状态 · 可配置
            </div>
            <Link to="/" className="admin-side-exit">
              <LogOut className="h-3.5 w-3.5" />
              返回前台
            </Link>
          </div>
        </aside>

        <main className="admin-main">
          {!section ? (
            <AdminDashboard />
          ) : (
            <div className="space-y-5">
              {section === "pipeline" ? (
                <div className="space-y-5">
                  <AdminStepper
                    steps={PIPELINE_STEPS}
                    activeId={pipelineStep}
                    onSelect={(id) => goPipelineStep(id as PipelineStep)}
                  />
                  <div className="space-y-6">
                    {pipelineStep === "models" ? (
                      <div className="space-y-6">
                        <AdminClaudePage />
                        <AdminConfigsPage />
                      </div>
                    ) : null}
                    {pipelineStep === "fetch-network" ? <AdminFetchNetworkPage /> : null}
                    {pipelineStep === "fetch-settings" ? <AdminFetchSettingsPage /> : null}
                    {pipelineStep === "subtitle-slice" ? <AdminSubtitleSlicePage /> : null}
                    {pipelineStep === "source-overview" ? <AdminOverviewPage /> : null}
                    {pipelineStep === "draft" ? <AdminDraftStrategiesPanel /> : null}
                    {pipelineStep === "cover" ? <AdminCoverPage /> : null}
                    {pipelineStep === "vector" ? <AdminVectorPage /> : null}
                    {pipelineStep === "chat" ? <AdminChatPage /> : null}
                  </div>
                  <div className="admin-stepper-footer">
                    <Button
                      type="button"
                      variant="outline"
                      className="rounded-full"
                      disabled={stepIndex <= 0}
                      onClick={goPrevStep}
                    >
                      上一步
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      {stepIndex + 1} / {PIPELINE_STEPS.length}
                      <span className="mx-1.5 text-border">·</span>
                      各页保存按钮仍在页面内
                    </span>
                    <Button
                      type="button"
                      className="rounded-full"
                      disabled={stepIndex >= PIPELINE_STEPS.length - 1}
                      onClick={goNextStep}
                    >
                      下一步 →
                    </Button>
                  </div>
                </div>
              ) : null}

              {section === "observability" ? (
                <div className="space-y-5">
                  <nav className="admin-tab-nav" aria-label="运行观测">
                    {OBS_TABS.map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => goObsTab(t.id)}
                        className={cn(
                          "admin-tab-item",
                          obsTab === t.id ? "admin-tab-item-active" : "admin-tab-item-idle",
                        )}
                      >
                        {t.label}
                      </button>
                    ))}
                  </nav>
                  {obsTab === "pipeline-logs" ? <AdminPipelineLogsPage /> : null}
                  {obsTab === "llm-traces" ? <AdminLlmTracesPage /> : null}
                </div>
              ) : null}

              {section === "settings" ? <AdminSettingsPage /> : null}
              {section === "accounts" ? <AdminUsersPage /> : null}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function AdminStepper({
  steps,
  activeId,
  onSelect,
}: {
  steps: { id: string; label: string; hint: string }[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  const activeIndex = steps.findIndex((s) => s.id === activeId);
  return (
    <nav className="admin-stepper" aria-label="内容流水线步骤">
      <ol className="admin-stepper-list">
        {steps.map((step, index) => {
          const state =
            index === activeIndex ? "active" : index < activeIndex ? "done" : "idle";
          return (
            <li key={step.id} className="admin-stepper-item">
              {index > 0 ? <span className="admin-stepper-connector" aria-hidden /> : null}
              <button
                type="button"
                title={step.hint}
                onClick={() => onSelect(step.id)}
                className={cn("admin-stepper-btn", `admin-stepper-btn-${state}`)}
              >
                <span className="admin-stepper-index">{index + 1}</span>
                <span className="admin-stepper-label">{step.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
