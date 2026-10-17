import { Link, useNavigate } from "react-router-dom";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { AdminUsersPage } from "@/pages/admin-users";
import { AdminConfigsPage } from "@/pages/admin-configs";

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
          <h1 className="text-2xl font-semibold tracking-tight">后台（admin）</h1>
          <p className="text-sm text-muted-foreground">
            账号 / 模型配置 / Skills / Agents 的统一入口。
          </p>
        </div>

        <AdminConfigsPage />
        <AdminUsersPage />
      </div>
    </Layout>
  );
}
