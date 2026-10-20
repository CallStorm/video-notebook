interface UserAvatarProps {
  name?: string | null;
  size?: "sm" | "md";
}

export function UserAvatar({ name, size = "md" }: UserAvatarProps) {
  const initials = computeInitials(name);
  const dim = size === "sm" ? "h-7 w-7 text-xs" : "h-9 w-9 text-sm";
  return (
    <div
      className={`flex ${dim} shrink-0 items-center justify-center rounded-full bg-primary font-medium text-primary-foreground`}
      title={name ?? ""}
    >
      {initials}
    </div>
  );
}

function computeInitials(name?: string | null): string {
  if (!name) return "?";
  // 去掉前后空白，对中文 / 英文统一取前 2 字符
  const trimmed = name.trim();
  if (!trimmed) return "?";
  // 对中文 / 日文 / 韩文（CJK 范围）直接取前 2 个字符；否则按空格切词取首字母
  if (/[㐀-鿿぀-ヿ가-힯]/.test(trimmed)) {
    return trimmed.slice(0, 2);
  }
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return trimmed.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
