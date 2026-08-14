import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  request,
  updateAIPreferences,
  type AIPreferences,
} from "../api";

interface AuthUser {
  id: number;
  username: string;
  email: string;
  is_verified: boolean;
  is_developer: boolean;
  ai_processing_consent: boolean;
  ai_redaction_enabled: boolean;
}

interface RegisterResult {
  id: number;
  username: string;
  email: string;
  is_verified: boolean;
  message: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<RegisterResult>;
  resendVerification: (email: string) => Promise<string>;
  updateAIPrivacy: (
    processingConsent: boolean,
    redactionEnabled: boolean,
  ) => Promise<AIPreferences>;
  verifyEmail: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    request<AuthUser>("/api/auth/me", {
      method: "GET",
    })
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function login(identifier: string, password: string) {
    await request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: identifier, password }),
    });
    setUser(await request<AuthUser>("/api/auth/me"));
    setIsLoading(false);
  }

  async function register(
    username: string,
    email: string,
    password: string,
  ): Promise<RegisterResult> {
    const res = await request<RegisterResult>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    return res;
  }

  async function verifyEmail(verifyToken: string) {
    await request<{
      id: number;
      username: string;
      email: string;
      is_verified: boolean;
      is_developer: boolean;
      ai_processing_consent: boolean;
      ai_redaction_enabled: boolean;
    }>("/api/auth/verify", {
      method: "POST",
      body: JSON.stringify({ token: verifyToken }),
    });
  }

  async function resendVerification(email: string): Promise<string> {
    const response = await request<{ message: string }>(
      "/api/auth/verification/resend",
      {
        method: "POST",
        body: JSON.stringify({ email }),
      },
    );
    return response.message;
  }

  async function updateAIPrivacy(
    processingConsent: boolean,
    redactionEnabled: boolean,
  ): Promise<AIPreferences> {
    const preferences = await updateAIPreferences(
      processingConsent,
      redactionEnabled,
    );
    setUser((current) =>
      current
        ? {
            ...current,
            ai_processing_consent: preferences.processing_consent,
            ai_redaction_enabled: preferences.redaction_enabled,
          }
        : current,
    );
    return preferences;
  }

  async function logout() {
    await request("/api/auth/logout", { method: "POST" });
    setUser(null);
    setIsLoading(false);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      login,
      register,
      resendVerification,
      updateAIPrivacy,
      verifyEmail,
      logout,
    }),
    [user, isLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
