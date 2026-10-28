import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useMemo } from "react";
import {
  Cable,
  Home,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings2,
  Sparkles,
  Users,
  Waypoints,
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
import { AdminStudioPanel } from "@/pages/admin-studio";
import { AdminDashboard } from "@/pages/admin-dashboard";
import { cn } from "@/lib/utils";

type AdminSection =
  | "pipeline"
  | "studio"
  | "pipeline-logs"
  | "llm-traces"
  | "settings"
  | "accounts";

type PipelineStep =
  | "models"
  | "fetch-network"
  | "fetch-settings"
  | "subtitle-slice"
  | "source-overview"
  | "cover"
  | "vector"
  | "chat";

const PIPELINE_STEPS: { id: PipelineStep; label: string; hint: string }[] = [
  { id: "models", label: "模型", hint: "模型与 Claude Code" },
  { id: "fetch-network", label: "网络", hint: "Cookie 与代理" },
  { id: "fetch-settings", label: "抓取", hint: "并发与分块" },
  { id: "subtitle-slice", label: "切片", hint: "ASR 切段" },
  { id: "source-overview", label: "概览", hint: "自动概览与提示词" },
  { id: "cover", label: "封面", hint: "SVG 封面提示词" },
  { id: "vector", label: "向量", hint: "语义索引" },
  { id: "chat", label: "对话", hint: "历史轮数" },
];

const SIDE_NAV: {
  id: "home" | AdminSection;
  label: string;
  icon: typeof Home;
}[] = [
  { id: "home", label: "首页", icon: Home },
  { id: "pipeline", label: "抓取流水线", icon: Cable },
  { id: "studio", label: "Studio 能力", icon: Sparkles },
  { id: "pipeline-logs", label: "流水线日志", icon: ScrollText },
  { id: "llm-traces", label: "LLM 追踪", icon: Waypoints },
  { id: "settings", label: "系统设置", icon: Settings2 },
  { id: "accounts", label: "账号管理", icon: Users },
];


/** 旧 ?tab= 映射到 section + step/tab */
const OLD_TAB_MAP: Record<
  string,
  { section: AdminSection; step?: PipelineStep; tab?: string }
> = {
  overview: { section: "pipeline", step: "models" },
  models: { section: "pipeline", step: "models" },
  "fetch-network": { section: "pipeline", step: "fetch-network" },
  "fetch-settings": { section: "pipeline", step: "fetch-settings" },
  "subtitle-slice": { section: "pipeline", step: "subtitle-slice" },
  "source-overview": { section: "pipeline", step: "source-overview" },
  cover: { section: "pipeline", step: "cover" },
  vector: { section: "pipeline", step: "vector" },
  chat: { section: "pipeline", step: "chat" },
  skills: { section: "studio" },
  agents: { section: "studio" },
  studio: { section: "studio" },
  accounts: { section: "accounts" },
  "pipeline-logs": { section: "pipeline-logs" },
  "llm-traces": { section: "llm-traces" },
  settings: { section: "settings" },
};

function isSection(v: string | null): v is AdminSection {
  return (
    v === "pipeline" ||
    v === "studio" ||
    v === "pipeline-logs" ||
    v === "llm-traces" ||
    v === "settings" ||
    v === "accounts"
  );
}

function isPipelineStep(v: string | null): v is PipelineStep {
  return PIPELINE_STEPS.some((s) => s.id === v);
}

function paramsFor(
  section: AdminSection,
  opts?: { step?: PipelineStep; tab?: string },
): Record<string, string> {
  if (section === "pipeline") {
    return { section, step: opts?.step ?? "models" };
  }
  if (section === "studio") {
    return { section };
  }
  return { section };
}

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // 兼容旧书签：?tab=xxx、section=observability|system
  useEffect(() => {
    const oldTab = searchParams.get("tab");
    const sectionNow = searchParams.get("section");

    if (sectionNow === "observability") {
      const next =
        oldTab === "llm-traces"
          ? "llm-traces"
          : oldTab === "pipeline-logs"
            ? "pipeline-logs"
            : "pipeline-logs";
      setSearchParams(paramsFor(next), { replace: true });
      return;
    }

    if (sectionNow === "system") {
      if (oldTab === "pipeline-logs" || oldTab === "llm-traces") {
        setSearchParams(paramsFor(oldTab), { replace: true });
        return;
      }
      if (oldTab === "settings") {
        setSearchParams(paramsFor("settings"), { replace: true });
        return;
      }
      setSearchParams(paramsFor("accounts"), { replace: true });
      return;
    }

    const hasSection = isSection(sectionNow);
    if (!oldTab || hasSection) return;
    const mapped = OLD_TAB_MAP[oldTab];
    if (!mapped) return;
    setSearchParams(paramsFor(mapped.section, { step: mapped.step, tab: mapped.tab }), {
      replace: true,
    });
  }, [searchParams, setSearchParams]);

  const sectionRaw = searchParams.get("section");
  const section = isSection(sectionRaw) ? sectionRaw : null;
  const sideActive: "home" | AdminSection = section ?? "home";

  const pipelineStep: PipelineStep = isPipelineStep(searchParams.get("step"))
    ? (searchParams.get("step") as PipelineStep)
    : "models";

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
              className="rounded-full border border-border/60 bg-card px-3 py-1 text-xs font-medium text-foreground shadow-soft transition hover:border-primary/30 hover:text-primary"
            >
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
          <div className="admin-side-brand">
            <span className="admin-side-brand-icon" aria-hidden>
              <LayoutDashboard className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold tracking-tight text-foreground">
                视频笔记
              </div>
              <div className="truncate text-[11px] text-muted-foreground">管理配置中心</div>
            </div>
          </div>

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

              {section === "studio" ? <AdminStudioPanel /> : null}

              {section === "pipeline-logs" ? <AdminPipelineLogsPage /> : null}
              {section === "llm-traces" ? <AdminLlmTracesPage /> : null}
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
    <nav className="admin-stepper" aria-label="抓取流水线步骤">
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
