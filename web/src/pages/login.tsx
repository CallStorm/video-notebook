import { Link } from "react-router-dom";
import {
  BookOpen,
  Clapperboard,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { LoginForm } from "@/components/login-form";

const STEPS = [
  {
    icon: Clapperboard,
    title: "导入视频",
    desc: "上传或粘贴链接，自动字幕与概览",
    tone: "bg-primary/10 text-primary",
  },
  {
    icon: MessageSquareText,
    title: "提问对话",
    desc: "对着内容追问，引用可跳回原片",
    tone: "bg-[hsl(172_50%_94%)] text-[hsl(var(--success))]",
  },
  {
    icon: Sparkles,
    title: "Studio 产出",
    desc: "一键生成导图、幻灯片与笔记",
    tone: "bg-[hsl(258_80%_96%)] text-[hsl(var(--violet))]",
  },
];

export default function LoginPage() {
  return (
    <div className="login-mesh relative flex min-h-screen flex-col overflow-hidden lg:flex-row">
      {/* 氛围光斑 */}
      <div
        className="login-orb -left-24 top-10 h-72 w-72 bg-primary/25"
        aria-hidden
      />
      <div
        className="login-orb right-[-4rem] top-24 h-80 w-80 bg-[hsl(var(--violet)/0.22)]"
        style={{ animationDelay: "1.2s" }}
        aria-hidden
      />
      <div
        className="login-orb bottom-[-3rem] left-1/3 h-64 w-64 bg-[hsl(var(--success)/0.18)]"
        style={{ animationDelay: "2.4s" }}
        aria-hidden
      />

      {/* 左：产品介绍 */}
      <aside className="relative z-10 flex flex-1 flex-col justify-center px-8 py-12 lg:px-14 xl:px-20">
        <div className="mx-auto w-full max-w-lg animate-fade-up space-y-8 lg:mx-0">
          <Brand />
          <div className="space-y-3">
            <p className="inline-flex items-center gap-1.5 rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              视频笔记
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              把长视频变成可提问的笔记本
            </h1>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
              上传或粘贴链接，提问与记笔记，并生成导图、幻灯片。
            </p>
          </div>
          <ul className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, desc, tone }) => (
              <li
                key={title}
                className="group flex gap-3 rounded-2xl border border-border/50 bg-card/75 p-3.5 shadow-soft backdrop-blur-md transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/20 hover:shadow-soft-md"
              >
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${tone}`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{title}</p>
                  <p className="mt-0.5 text-xs leading-snug text-muted-foreground">
                    {desc}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          <p className="hidden items-center gap-2 text-xs text-muted-foreground lg:flex">
            <BookOpen className="h-3.5 w-3.5" />
            内部使用 · 账号由管理员开通
          </p>
        </div>
      </aside>

      {/* 右：登录卡 */}
      <section className="relative z-10 flex flex-1 items-center justify-center px-4 py-10 lg:px-10">
        <div className="w-full max-w-sm animate-fade-up space-y-5" style={{ animationDelay: "80ms" }}>
          <div className="space-y-1 text-center lg:text-left">
            <h2 className="text-xl font-semibold tracking-tight">欢迎回来</h2>
            <p className="text-sm text-muted-foreground">
              账号由管理员创建。如还未开通，请联系管理员。
            </p>
          </div>
          <LoginForm />
          <p className="text-center lg:text-left">
            <Link
              to="/"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              返回首页
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
