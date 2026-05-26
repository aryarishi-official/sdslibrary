import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Pages
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";

import SdsPage from "@/pages/SdsPage";
import SdsDetailPage from "@/pages/SdsDetailPage";
import SearchPage from "@/pages/SearchPage";


// ─── JWT helpers ──────────────────────────────────────────────────────────────

type JwtPayload = {
  role?: string;
  sub?: string;
  exp?: number;
};

function parseJwt(token: string): JwtPayload | null {
  try {
    const base64 = token.split(".")[1];
    if (!base64) return null;
    const json = atob(base64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

function getToken(): string | null {
  return localStorage.getItem("token") ?? sessionStorage.getItem("token")
}

function getUserRole(): string | null {
  const token = getToken();
  if (!token) return null;
  const payload = parseJwt(token);
  if (!payload) return null;
  // Check token expiry
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    localStorage.removeItem("token");
    return null;
  }
  return payload.role ?? null;
}

// ─── ProtectedRoute ───────────────────────────────────────────────────────────

type ProtectedRouteProps = {
  allowedRoles?: string[];
};

function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const token = getToken();

  if (!token) {
    // No active session → back to homepage (where the login dialog lives)
    return <Navigate to="/" replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const role = getUserRole();
    if (!role || !allowedRoles.includes(role)) {
      return <Navigate to="/" replace />;
    }
  }

  return <Outlet />;
}

// ─── Query client (singleton) ─────────────────────────────────────────────────

const queryClient = new QueryClient();

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Navigate to="/sds" replace />} />
          <Route path="/signup" element={<Navigate to="/login" replace />} />


          {/* Protected routes — any authenticated user */}
          <Route element={<ProtectedRoute />}>
            <Route path="/sds" element={<SdsPage />} />
            <Route path="/sds/:id" element={<SdsDetailPage />} />
            <Route path="/search" element={<SearchPage />} />

          </Route>

          {/* Admin-only example (extend as needed) */}
          {/* <Route element={<ProtectedRoute allowedRoles={["Admin"]} />}>
            <Route path="/admin" element={<AdminPage />} />
          </Route> */}

          {/* 404 */}

        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
