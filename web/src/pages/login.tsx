import { Link } from "react-router-dom";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="w-full max-w-sm space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">登录</h1>
        <p className="text-sm text-muted-foreground">
          内部使用，账号由管理员创建。如还未开通，请联系管理员。
        </p>
      </div>
      <LoginForm />
      <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
        返回首页
      </Link>
    </div>
  );
}
