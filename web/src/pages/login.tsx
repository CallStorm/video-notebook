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
    title: "分析视频",
    desc: "上传或粘贴链接，自动字幕与概览",
  },
  {
    icon: MessageSquareText,
    title: "学习提问",
    desc: "对着内容追问，引用可跳回原片",
  },
  {
    icon: Sparkles,
    title: "Studio 输出",
    desc: "一键生成导图、幻灯片与笔记",
  },
];

export default function LoginPage() {
  return (
    <div className="login-mesh relative flex min-h-screen flex-col lg:flex-row">
      {/* 左：价值主张 */}
      <aside className="relative flex flex-1 flex-col justify-center px-8 py-12 lg:px-14 xl:px-20">
        <div className="mx-auto w-full max-w-lg space-y-8 lg:mx-0">
          <Brand />
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              把长视频变成可提问、
              <br className="hidden sm:block" />
              可输出的学习笔记本
            </h1>
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
              分析 → 学习 → 输出。适合本地部署的视频学习工作台，帮你把会议、课程与教程沉淀成知识。
            </p>
          </div>
          <ul className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, desc }) => (
              <li
                key={title}
                className="flex gap-3 rounded-2xl border border-border/60 bg-card/80 p-3.5 shadow-soft backdrop-blur-sm"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
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
      <section className="flex flex-1 items-center justify-center px-4 py-10 lg:px-10">
        <div className="w-full max-w-sm space-y-5">
          <div className="space-y-1 text-center lg:text-left">
            <h2 className="text-xl font-semibold tracking-tight">登录</h2>
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
