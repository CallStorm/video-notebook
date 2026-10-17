import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  Outlet,
} from "react-router-dom";
import HomePage from "@/pages/home";
import LoginPage from "@/pages/login";
import AdminPage from "@/pages/admin";
import DiscoverPage from "@/pages/discover";
import NotebookPage from "@/pages/notebook";
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
      { path: "/", element: <HomePage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/discover", element: <DiscoverPage /> },
      {
        path: "/notebooks/:id",
        element: (
          <RequireAuth>
            <NotebookPage />
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
      // 兜底：未匹配路由 → 首页
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}