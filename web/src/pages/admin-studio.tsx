import { Navigate } from "react-router-dom";

/** Studio 能力后台配置已移除；PPT / 思维导图固定启用。 */
export function AdminStudioPanel() {
  return <Navigate to="/admin" replace />;
}

/** 兼容旧链接 → 后台首页 */
export default function AdminStudioPage() {
  return <Navigate to="/admin" replace />;
}
