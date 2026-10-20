import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { AdminClaudePage } from "@/pages/admin-claude";
import { AdminUsersPage } from "@/pages/admin-users";
import { AdminConfigsPage } from "@/pages/admin-configs";
import { AdminFetchNetworkPage } from "@/pages/admin-fetch-network";
import { AdminFetchSettingsPage } from "@/pages/admin-fetch-settings";
import { AdminSkillsPanel } from "@/pages/admin-skills";
import { AdminAgentsPanel } from "@/pages/admin-agents";
import { AdminStudioPanel } from "@/pages/admin-studio";

type AdminTab =
  | "overview"
  | "fetch-network"
  | "fetch-settings"
  | "accounts"
  | "skills"
  | "agents"
  | "studio";

const TABS: { id: AdminTab; label: string }[] = [
  { id: "overview", label: "概览" },
  { id: "fetch-network", label: "抓取与网络" },
  { id: "fetch-settings", label: "抓取设置" },
  { id: "accounts", label: "账号" },
  { id: "skills", label: "技能" },
  { id: "agents", label: "智能体" },
  { id: "studio", label: "Studio 能力" },
];

function parseTab(raw: string | null): AdminTab {
  if (
    raw === "skills" ||
    raw === "agents" ||
    raw === "studio" ||
    raw === "overview" ||
    raw === "fetch-network" ||
    raw === "fetch-settings" ||
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
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>{user?.name}</span>
          <Link to="/" className="hover:text-foreground">
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
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">后台</h1>
          <p className="text-sm text-muted-foreground">
            模型、抓取网络、账号、技能、智能体与 Studio 能力管理。
          </p>
          <nav className="mt-4 flex flex-wrap gap-1 rounded-full bg-muted/50 p-1 w-fit">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                  tab === item.id
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        {tab === "overview" ? (
          <div className="space-y-6">
            <AdminClaudePage />
            <AdminConfigsPage />
          </div>
        ) : null}
        {tab === "fetch-network" ? <AdminFetchNetworkPage /> : null}
        {tab === "fetch-settings" ? <AdminFetchSettingsPage /> : null}
        {tab === "accounts" ? <AdminUsersPage /> : null}
        {tab === "skills" ? <AdminSkillsPanel /> : null}
        {tab === "agents" ? <AdminAgentsPanel /> : null}
        {tab === "studio" ? <AdminStudioPanel /> : null}
      </div>
    </Layout>
  );
}
