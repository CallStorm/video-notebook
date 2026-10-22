import { Brand } from "@/components/brand";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="login-mesh relative flex min-h-screen flex-col overflow-hidden lg:flex-row">
      {/* 极光装饰层：光球 / 玻璃片 / 轨道 / 波形 */}
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
        <div className="login-orb login-orb-float -left-24 top-8 h-72 w-72 bg-primary/30" />
        <div
          className="login-orb login-orb-float right-[-5rem] top-12 h-[22rem] w-[22rem] bg-[hsl(var(--violet)/0.28)]"
          style={{ animationDelay: "-2.2s" }}
        />
        <div
          className="login-orb login-orb-float bottom-[-5rem] left-[26%] h-80 w-80 bg-[hsl(var(--success)/0.22)]"
          style={{ animationDelay: "-4.4s" }}
        />
        <div
          className="login-orb login-orb-float left-[48%] top-[36%] h-36 w-36 bg-primary/18"
          style={{ animationDelay: "-1.1s" }}
        />

        <div className="login-pane login-pane-a left-[7%] top-[20%] hidden lg:block" />
        <div className="login-pane login-pane-b left-[20%] top-[56%] hidden lg:block" />
        <div className="login-pane login-pane-c right-[40%] top-[16%] hidden lg:block" />

        <div className="login-orbit left-[5%] top-[28%] hidden lg:block" />

        <svg
          className="login-wave absolute bottom-[14%] left-[5%] hidden w-[min(420px,42vw)] text-primary/30 lg:block"
          viewBox="0 0 420 56"
          fill="none"
        >
          <path
            d="M0 28 C 42 10, 84 46, 126 28 S 210 10, 252 28 S 336 46, 378 28 S 410 14, 420 28"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="5 7"
            strokeLinecap="round"
          />
          <path
            className="login-wave-line"
            d="M0 34 C 52 16, 96 42, 148 30 S 236 14, 286 30 S 360 44, 420 26"
            stroke="currentColor"
            strokeWidth="1.25"
            opacity="0.55"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {/* 左：极简文案 */}
      <aside className="relative z-10 flex flex-1 flex-col justify-center px-8 py-12 lg:px-14 xl:px-20">
        <div className="mx-auto w-full max-w-md animate-fade-up space-y-7 lg:mx-0">
          <Brand />
          <div className="space-y-4">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl lg:text-[2.55rem] lg:leading-[1.15]">
              把长视频变成笔记本
            </h1>
            <div
              className="login-title-bar h-1 w-24 rounded-full bg-gradient-to-r from-primary/80 via-primary/35 to-transparent"
              aria-hidden
            />
          </div>
        </div>
      </aside>

      {/* 右：磨砂登录卡 */}
      <section className="relative z-10 flex flex-1 items-center justify-center px-4 py-10 lg:px-10">
        <div
          className="w-full max-w-sm animate-fade-up space-y-4"
          style={{ animationDelay: "80ms" }}
        >
          <h2 className="text-center text-xl font-semibold tracking-tight lg:text-left">
            欢迎回来
          </h2>
          <LoginForm />
        </div>
      </section>
    </div>
  );
}
