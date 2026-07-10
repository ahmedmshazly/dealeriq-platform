"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { ApiResponse } from "./api-types";
import { setAccessToken } from "./token-store";

type UserProfile = ApiResponse<"/api/v1/auth/me", "get">;

interface AuthContextValue {
  user: UserProfile | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<{ mustChangePassword: boolean }>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const { data, error } = await api.GET("/api/v1/auth/me");
    setUser(error ? null : (data ?? null));
  }, []);

  useEffect(() => {
    // Attempt to restore a session from the httpOnly refresh cookie on page load.
    let cancelled = false;
    (async () => {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/refresh`,
        { method: "POST", credentials: "include" },
      );
      if (cancelled) return;
      if (res.ok) {
        const body: { access_token: string } = await res.json();
        setAccessToken(body.access_token);
        await refreshUser();
      }
      setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data, error } = await api.POST("/api/v1/auth/login", {
        body: { email, password },
      });
      if (error || !data) {
        throw new Error("Invalid email or password.");
      }
      setAccessToken(data.access_token);
      await refreshUser();
      return { mustChangePassword: data.must_change_password };
    },
    [refreshUser],
  );

  const logout = useCallback(async () => {
    await api.POST("/api/v1/auth/logout");
    setAccessToken(null);
    setUser(null);
  }, []);

  const logoutAll = useCallback(async () => {
    await api.POST("/api/v1/auth/logout-all");
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, logoutAll, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
