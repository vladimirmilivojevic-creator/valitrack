import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setCsrfToken, setUnauthorizedHandler } from "./api";
import type { Session, User } from "./types";

interface AuthState {
  user: User | null;
  permissions: string[];
  loading: boolean;
  can: (permission: string) => boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const apply = useCallback((next: Session | null) => {
    setCsrfToken(next?.csrf_token ?? "");
    setSession(next);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      apply(null);
      queryClient.clear();
    });
    api
      .get<Session>("/auth/me")
      .then(apply)
      .catch(() => apply(null))
      .finally(() => setLoading(false));
    return () => setUnauthorizedHandler(null);
  }, [apply, queryClient]);

  const value = useMemo<AuthState>(
    () => ({
      user: session?.user ?? null,
      permissions: session?.permissions ?? [],
      loading,
      can: (permission) => (session?.permissions ?? []).includes(permission),
      login: async (username, password) => {
        const next = await api.post<Session>("/auth/login", { username, password });
        queryClient.clear();
        apply(next);
      },
      logout: async () => {
        await api.post("/auth/logout");
        queryClient.clear();
        apply(null);
      },
    }),
    [session, loading, apply, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
