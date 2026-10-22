import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  Outlet,
} from "react-router-dom";
import HomePage from "@/pages/home";
import LoginPage from "@/pages/login";
import AdminPage from "@/pages/admin";
import AdminSkillsPage from "@/pages/admin-skills";
import AdminAgentsPage from "@/pages/admin-agents";
import AdminStudioPage from "@/pages/admin-studio";
import DiscoverPage from "@/pages/discover";
import SearchPage from "@/pages/search";
import NotebookPage from "@/pages/notebook";
import CollectionPage from "@/pages/collection";
import { RequireAuth } from "@/components/require-auth";
import { AuthProvider } from "@/lib/auth";

/**
 * AuthProvider 放在 root layout 内部，这样 useNavigate 才有 context。
 */
function RootLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        path: "/",
        element: (
          <RequireAuth>
            <HomePage />
          </RequireAuth>
        ),
      },
      { path: "/login", element: <LoginPage /> },
      {
        path: "/discover",
        element: (
          <RequireAuth>
            <DiscoverPage />
          </RequireAuth>
        ),
      },
      {
        path: "/search",
        element: (
          <RequireAuth>
            <SearchPage />
          </RequireAuth>
        ),
      },
      {
        path: "/notebooks/:id",
        element: (
          <RequireAuth>
            <NotebookPage />
          </RequireAuth>
        ),
      },
      {
        path: "/collections/:id",
        element: (
          <RequireAuth>
            <CollectionPage />
          </RequireAuth>
        ),
      },
      {
        path: "/admin",
        element: (
          <RequireAuth admin>
            <AdminPage />
          </RequireAuth>
        ),
      },
      {
        path: "/admin/skills",
        element: (
          <RequireAuth admin>
            <AdminSkillsPage />
          </RequireAuth>
        ),
      },
      {
        path: "/admin/agents",
        element: (
          <RequireAuth admin>
            <AdminAgentsPage />
          </RequireAuth>
        ),
      },
      {
        path: "/admin/studio",
        element: (
          <RequireAuth admin>
            <AdminStudioPage />
          </RequireAuth>
        ),
      },
      // 兜底：未匹配路由 → 首页（未登录会由 RequireAuth 再跳登录）
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
