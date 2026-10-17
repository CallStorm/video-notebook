import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Brand } from "@/components/brand";
import { UserAvatar } from "@/components/user-avatar";
import { Card, CardContent } from "@/components/ui/card";

export default function DiscoverPage() {
  const { user, access } = useAuth();
  const token = access ?? "";
  if (!token) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Card>
          <CardContent className="pt-6 text-sm">
            请先登录。
            <div className="mt-3">
              <Link className="text-blue-600 underline" to="/login">
                跳到登录页
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-6">
          <Link to="/">
            <Brand />
          </Link>
          <div className="ml-auto">
            <UserAvatar name={user?.name} />
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl p-6">
        <h1 className="mb-4 text-2xl font-semibold">发现</h1>
        <div className="rounded-lg border border-dashed bg-muted/20 p-16 text-center text-sm text-muted-foreground">
          公开笔记本浏览 / Discover 留 Phase 12 实装（依赖 share_all 公开流）。
        </div>
      </div>
    </div>
  );
}
