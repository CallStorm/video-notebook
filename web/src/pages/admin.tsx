import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { AdminClaudePage } from "@/pages/admin-claude";
import { AdminUsersPage } from "@/pages/admin-users";
import { AdminConfigsPage } from "@/pages/admin-configs";
import { AdminFetchNetworkPage } from "@/pages/admin-fetch-network";
import { AdminFetchSettingsPage } from "@/pages/admin-fetch-settings";
import { AdminSubtitleSlicePage } from "@/pages/admin-subtitle-slice";
import { AdminOverviewPage } from "@/pages/admin-overview";
import { AdminVectorPage } from "@/pages/admin-vector";
import { AdminSkillsPanel } from "@/pages/admin-skills";
import { AdminAgentsPanel } from "@/pages/admin-agents";
import { AdminStudioPanel } from "@/pages/admin-studio";

type AdminTab =
  | "overview"
  | "fetch-network"
  | "fetch-settings"
  | "subtitle-slice"
  | "source-overview"
  | "vector"
  | "accounts"
  | "skills"
  | "agents"
  | "studio";

const TABS: { id: AdminTab; label: string; hint: string }[] = [
  { id: "overview", label: "概览", hint: "模型与 Claude Code" },
  { id: "fetch-network", label: "抓取与网络", hint: "Cookie 与代理" },
  { id: "fetch-settings", label: "抓取设置", hint: "并发与分块" },
  { id: "subtitle-slice", label: "语音切片", hint: "ASR 切段" },
  { id: "source-overview", label: "来源概览", hint: "自动概览与提示词" },
  { id: "vector", label: "向量配置", hint: "语义索引" },
  { id: "accounts", label: "账号", hint: "用户管理" },
  { id: "skills", label: "技能", hint: "技能包上传" },
  { id: "agents", label: "智能体", hint: "提示与超时" },
  { id: "studio", label: "Studio 能力", hint: "产物与表单" },
];

function parseTab(raw: string | null): AdminTab {
  if (
    raw === "skills" ||
    raw === "agents" ||
    raw === "studio" ||
    raw === "overview" ||
    raw === "fetch-network" ||
    raw === "fetch-settings" ||
    raw === "subtitle-slice" ||
    raw === "source-overview" ||
    raw === "vector" ||
    raw === "accounts"
  ) {
    return raw;
  }
  return "overview";
}

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = parseTab(searchParams.get("tab"));
  const active = TABS.find((item) => item.id === tab) ?? TABS[0];

  function setTab(next: AdminTab) {
    if (next === "overview") {
      setSearchParams({}, { replace: true });
    } else {
      setSearchParams({ tab: next }, { replace: true });
    }
  }

  return (
    <Layout
      rightSlot={
        <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
          <span className="hidden sm:inline max-w-[10rem] truncate">{user?.name}</span>
          <Link
            to="/"
            className="rounded-full border border-border/60 bg-card px-3 py-1 text-xs font-medium text-foreground shadow-soft transition hover:border-primary/30 hover:text-primary"
          >
            返回前台
          </Link>
          <Button
            size="sm"
            variant="outline"
            className="rounded-full"
            onClick={() => {
              logout();
              navigate("/", { replace: true });
            }}
          >
            登出
          </Button>
        </div>
      }
    >
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <div className="space-y-4">
          <nav className="admin-tab-nav w-fit" aria-label="后台分区">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                title={item.hint}
                onClick={() => setTab(item.id)}
                className={`admin-tab-item ${
                  tab === item.id ? "admin-tab-item-active" : "admin-tab-item-idle"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="space-y-6">
          {tab === "overview" ? (
            <div className="space-y-6">
              <AdminClaudePage />
              <AdminConfigsPage />
            </div>
          ) : null}
          {tab === "fetch-network" ? <AdminFetchNetworkPage /> : null}
          {tab === "fetch-settings" ? <AdminFetchSettingsPage /> : null}
          {tab === "subtitle-slice" ? <AdminSubtitleSlicePage /> : null}
          {tab === "source-overview" ? <AdminOverviewPage /> : null}
          {tab === "vector" ? <AdminVectorPage /> : null}
          {tab === "accounts" ? <AdminUsersPage /> : null}
          {tab === "skills" ? <AdminSkillsPanel /> : null}
          {tab === "agents" ? <AdminAgentsPanel /> : null}
          {tab === "studio" ? <AdminStudioPanel /> : null}
        </div>
      </div>
    </Layout>
  );
}
