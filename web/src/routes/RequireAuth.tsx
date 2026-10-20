import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { Loading } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}
