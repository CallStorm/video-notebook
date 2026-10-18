import { Link } from "react-router-dom";
import { Brand } from "@/components/brand";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <Brand />
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight">登录</h1>
            <p className="text-sm text-muted-foreground">
              内部使用，账号由管理员创建。如还未开通，请联系管理员。
            </p>
          </div>
        </div>
        <LoginForm />
        <p className="text-center">
          <Link
            to="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            返回首页
          </Link>
        </p>
      </div>
    </div>
  );
}
