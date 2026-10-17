import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ children, admin = false }: { children: React.ReactNode; admin?: boolean }) {
  const { user, access } = useAuth();
  const location = useLocation();

  if (!user || !access) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  if (admin && user.role !== "admin") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
