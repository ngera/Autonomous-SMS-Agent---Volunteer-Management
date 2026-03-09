import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/use-auth";
import type { AdminRole } from "@/types/enums";

interface RoleGateProps {
  minimum: AdminRole;
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGate({ minimum, children, fallback }: RoleGateProps) {
  const { hasRole } = useAuth();

  if (!hasRole(minimum)) {
    if (fallback) return <>{fallback}</>;
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
