import { Notebook } from "lucide-react";

export function Brand() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-gradient-to-br from-blue-500 via-emerald-500 to-amber-500 text-white">
        <Notebook className="h-5 w-5" />
      </div>
      <span className="text-lg font-semibold tracking-tight">视频笔记</span>
    </div>
  );
}
