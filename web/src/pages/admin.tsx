import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useMemo } from "react";
import {
  Bot,
  Cable,
  Home,
  LayoutDashboard,
  LogOut,
  Settings2,
  Sparkles,
  Users,
} from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { UserMenu } from "@/components/user-menu";
import { useAuth } from "@/lib/auth";
import { AdminClaudePage } from "@/pages/admin-claude";
import { AdminUsersPage } from "@/pages/admin-users";
import { AdminConfigsPage } from "@/pages/admin-configs";
import { AdminFetchNetworkPage } from "@/pages/admin-fetch-network";
import { AdminFetchSettingsPage } from "@/pages/admin-fetch-settings";
import { AdminSubtitleSlicePage } from "@/pages/admin-subtitle-slice";
import { AdminOverviewPage } from "@/pages/admin-overview";
import { AdminChatPage } from "@/pages/admin-chat";
import { AdminVectorPage } from "@/pages/admin-vector";
import { AdminSkillsPanel } from "@/pages/admin-skills";
import { AdminAgentsPanel } from "@/pages/admin-agents";
import { AdminStudioPanel } from "@/pages/admin-studio";
import { cn } from "@/lib/utils";

type AdminSection = "pipeline" | "studio" | "system";

type PipelineStep =
  | "models"
  | "fetch-network"
  | "fetch-settings"
  | "subtitle-slice"
  | "source-overview"
  | "vector"
  | "chat";

type StudioTab = "skills" | "agents" | "studio";
type SystemTab = "accounts";

const PIPELINE_STEPS: { id: PipelineStep; label: string; hint: string }[] = [
  { id: "models", label: "模型", hint: "模型与 Claude Code" },
  { id: "fetch-network", label: "网络", hint: "Cookie 与代理" },
  { id: "fetch-settings", label: "抓取", hint: "并发与分块" },
  { id: "subtitle-slice", label: "切片", hint: "ASR 切段" },
  { id: "source-overview", label: "概览", hint: "自动概览与提示词" },
  { id: "vector", label: "向量", hint: "语义索引" },
  { id: "chat", label: "对话", hint: "历史轮数" },
];

const STUDIO_TABS: { id: StudioTab; label: string; hint: string }[] = [
  { id: "skills", label: "Skills", hint: "技能包上传" },
  { id: "agents", label: "Agents", hint: "提示与超时" },
  { id: "studio", label: "Studio 工作台", hint: "产物与表单" },
];

const SYSTEM_TABS: { id: SystemTab; label: string; hint: string }[] = [
  { id: "accounts", label: "账号", hint: "用户管理" },
];

const SIDE_NAV: {
  id: "home" | AdminSection;
  label: string;
  icon: typeof Home;
}[] = [
  { id: "home", label: "首页", icon: Home },
  { id: "pipeline", label: "抓取流水线", icon: Cable },
  { id: "studio", label: "Studio 能力", icon: Sparkles },
  { id: "system", label: "系统与账号", icon: Users },
];

const HUB_CARDS: {
  section: AdminSection;
  title: string;
  desc: string;
  cta: string;
  accent: string;
  footer: "pipeline" | "studio" | "system";
}[] = [
  {
    section: "pipeline",
    title: "抓取流水线",
    desc: "从视频源到笔记知识的全流程配置：模型、网络、抓取、切片、概览、向量、对话。",
    cta: "进入配置 →",
    accent: "admin-hub-card-pipeline",
    footer: "pipeline",
  },
  {
    section: "studio",
    title: "Studio 能力",
    desc: "AI 能力编排与内容工作台：技能包、智能体与 Studio 产物。",
    cta: "查看能力 →",
    accent: "admin-hub-card-studio",
    footer: "studio",
  },
  {
    section: "system",
    title: "系统与账号",
    desc: "后台账号与权限管理。",
    cta: "进入管理 →",
    accent: "admin-hub-card-system",
    footer: "system",
  },
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
  vector: { section: "pipeline", step: "vector" },
  chat: { section: "pipeline", step: "chat" },
  skills: { section: "studio", tab: "skills" },
  agents: { section: "studio", tab: "agents" },
  studio: { section: "studio", tab: "studio" },
  accounts: { section: "system", tab: "accounts" },
};

function isSection(v: string | null): v is AdminSection {
  return v === "pipeline" || v === "studio" || v === "system";
}

function isPipelineStep(v: string | null): v is PipelineStep {
  return PIPELINE_STEPS.some((s) => s.id === v);
}

function isStudioTab(v: string | null): v is StudioTab {
  return v === "skills" || v === "agents" || v === "studio";
}

function isSystemTab(v: string | null): v is SystemTab {
  return v === "accounts";
}

function paramsFor(
  section: AdminSection,
  opts?: { step?: PipelineStep; tab?: string },
): Record<string, string> {
  if (section === "pipeline") {
    return { section, step: opts?.step ?? "models" };
  }
  if (section === "studio") {
    return { section, tab: opts?.tab ?? "skills" };
  }
  return { section, tab: opts?.tab ?? "accounts" };
}

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // 兼容旧书签 ?tab=xxx → 新 section/step
  useEffect(() => {
    const oldTab = searchParams.get("tab");
    const hasSection = isSection(searchParams.get("section"));
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

  const studioTab: StudioTab = isStudioTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as StudioTab)
    : "skills";

  const systemTab: SystemTab = isSystemTab(searchParams.get("tab"))
    ? (searchParams.get("tab") as SystemTab)
    : "accounts";

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

  function goStudioTab(tab: StudioTab) {
    setSearchParams(paramsFor("studio", { tab }), { replace: true });
  }

  function goSystemTab(tab: SystemTab) {
    setSearchParams(paramsFor("system", { tab }), { replace: true });
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

  const sectionTitle =
    section === "pipeline"
      ? "抓取流水线"
      : section === "studio"
        ? "Studio 能力"
        : section === "system"
          ? "系统与账号"
          : "三卡片总览";

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
          <div className="admin-main-head">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">后台配置</p>
              <h1 className="text-xl font-semibold tracking-tight text-foreground">
                {sectionTitle}
              </h1>
            </div>
          </div>

          {!section ? (
            <AdminHub
              onSelect={goSection}
              onStudioTab={(tab) => goStudioTab(tab)}
            />
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

              {section === "studio" ? (
                <div className="space-y-5">
                  <nav className="admin-tab-nav w-fit" aria-label="Studio 模块">
                    {STUDIO_TABS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        title={item.hint}
                        onClick={() => goStudioTab(item.id)}
                        className={cn(
                          "admin-tab-item",
                          studioTab === item.id
                            ? "admin-tab-item-active"
                            : "admin-tab-item-idle",
                        )}
                      >
                        {item.label}
                      </button>
                    ))}
                  </nav>
                  <div className="space-y-6">
                    {studioTab === "skills" ? <AdminSkillsPanel /> : null}
                    {studioTab === "agents" ? <AdminAgentsPanel /> : null}
                    {studioTab === "studio" ? <AdminStudioPanel /> : null}
                  </div>
                </div>
              ) : null}

              {section === "system" ? (
                <div className="space-y-5">
                  <nav className="admin-tab-nav w-fit" aria-label="系统模块">
                    {SYSTEM_TABS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        title={item.hint}
                        onClick={() => goSystemTab(item.id)}
                        className={cn(
                          "admin-tab-item",
                          systemTab === item.id
                            ? "admin-tab-item-active"
                            : "admin-tab-item-idle",
                        )}
                      >
                        {item.label}
                      </button>
                    ))}
                  </nav>
                  <div className="space-y-6">
                    {systemTab === "accounts" ? <AdminUsersPage /> : null}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function AdminHub({
  onSelect,
  onStudioTab,
}: {
  onSelect: (section: AdminSection) => void;
  onStudioTab: (tab: StudioTab) => void;
}) {
  return (
    <div className="space-y-6">
      <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
        按三大块组织配置入口。也可从左侧导航直接进入某一块。
      </p>
      <div className="admin-hub-grid">
        {HUB_CARDS.map((card) => (
          <div key={card.section} className={cn("admin-hub-card", card.accent)}>
            <div className="admin-hub-card-glow" aria-hidden />
            <div className="relative z-[1] flex h-full flex-col gap-3 text-left">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-semibold tracking-tight text-foreground">
                  {card.title}
                </h2>
                {card.section === "pipeline" ? (
                  <Bot className="h-5 w-5 text-primary/70" aria-hidden />
                ) : card.section === "studio" ? (
                  <Sparkles className="h-5 w-5 text-primary/70" aria-hidden />
                ) : (
                  <Settings2 className="h-5 w-5 text-primary/70" aria-hidden />
                )}
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{card.desc}</p>
              <button
                type="button"
                onClick={() => onSelect(card.section)}
                className={cn(
                  "mt-1 inline-flex w-fit items-center rounded-full px-3.5 py-1.5 text-xs font-medium transition",
                  card.section === "studio"
                    ? "border border-border/70 bg-card text-foreground hover:border-primary/30 hover:text-primary"
                    : "bg-primary text-primary-foreground shadow-soft hover:opacity-95",
                )}
              >
                {card.cta}
              </button>
              {card.footer === "pipeline" ? (
                <div className="mt-auto flex flex-wrap gap-1.5 border-t border-border/50 pt-3">
                  {PIPELINE_STEPS.map((s, i) => (
                    <span key={s.id} className="admin-hub-mini-step">
                      <span className="tabular-nums opacity-70">{i + 1}</span> {s.label}
                    </span>
                  ))}
                </div>
              ) : null}
              {card.footer === "studio" ? (
                <div className="mt-auto flex flex-wrap gap-2 border-t border-border/50 pt-3">
                  {STUDIO_TABS.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => onStudioTab(t.id)}
                      className="text-xs font-medium text-muted-foreground transition hover:text-primary"
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              ) : null}
              {card.footer === "system" ? (
                <div className="mt-auto border-t border-border/50 pt-3 text-xs text-muted-foreground">
                  账号 · 权限
                </div>
              ) : null}
            </div>
          </div>
        ))}
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
