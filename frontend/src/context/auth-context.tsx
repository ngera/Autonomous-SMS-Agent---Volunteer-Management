import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import api from "@/lib/api";
import { AdminRole } from "@/types/enums";
import { ROLE_HIERARCHY } from "@/lib/constants";
import type { TokenResponse } from "@/types/api";

interface AuthUser {
  id: string;
  email: string;
  role: AdminRole;
  tenant_id: string | null;
  tenant_name: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (minimumRole: AdminRole) => boolean;
}

export const AuthContext = createContext<AuthContextType | null>(null);

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function extractUserFromToken(token: string): AuthUser | null {
  const payload = decodeJwtPayload(token);
  if (!payload) return null;

  return {
    id: (payload.sub as string) || "",
    email: (payload.email as string) || "",
    role: ((payload.role as string) || "staff") as AdminRole,
    tenant_id: null,
    tenant_name: null,
  };
}

async function fetchUserProfile(): Promise<AuthUser | null> {
  try {
    const { data } = await api.get<{
      id: string;
      email: string;
      role: string;
      tenant_id: string | null;
      tenant_name: string | null;
    }>("/auth/me");
    return {
      id: data.id,
      email: data.email,
      role: data.role.toLowerCase() as AdminRole,
      tenant_id: data.tenant_id,
      tenant_name: data.tenant_name,
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount — fetch real role from backend
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      const decoded = extractUserFromToken(token);
      if (decoded) {
        // Set user immediately from token, then fetch real role
        setUser(decoded);
        fetchUserProfile().then((profile) => {
          if (profile) setUser(profile);
          setIsLoading(false);
        });
      } else {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        setIsLoading(false);
      }
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<TokenResponse>("/auth/login", {
      email,
      password,
    });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    // Fetch real role from backend
    const profile = await fetchUserProfile();
    setUser(profile || extractUserFromToken(data.access_token));
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Proceed with local logout even if API call fails
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (minimumRole: AdminRole): boolean => {
      if (!user) return false;
      return ROLE_HIERARCHY[user.role] >= ROLE_HIERARCHY[minimumRole];
    },
    [user]
  );

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      hasRole,
    }),
    [user, isLoading, login, logout, hasRole]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
