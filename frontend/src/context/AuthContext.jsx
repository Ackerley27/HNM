import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, setAccessToken } from "../services/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    function handleExpiredToken() {
      setAccessToken(null);
      setUser(null);
    }
    window.addEventListener("auth:expired", handleExpiredToken);
    return () => window.removeEventListener("auth:expired", handleExpiredToken);
  }, []);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    try {
      const { data: tokenData } = await api.post("/auth/login", { email, password });
      setAccessToken(tokenData.access_token);
      try {
        const { data: profile } = await api.get("/auth/me");
        setUser(profile);
        return profile;
      } catch (error) {
        setAccessToken(null);
        throw error;
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
