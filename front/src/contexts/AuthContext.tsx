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
  setToken,
  getToken,
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
  token: string | null;
  user: AuthUser | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<RegisterResult>;
  resendVerification: (email: string) => Promise<string>;
  updateAIPrivacy: (
    processingConsent: boolean,
    redactionEnabled: boolean,
  ) => Promise<AIPreferences>;
  verifyEmail: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    let cancelled = false;
    request<AuthUser>("/api/auth/me", {
      method: "GET",
    })
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          setTokenState(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function login(username: string, password: string) {
    const res = await request<{
      access_token: string;
      user_id: number;
      is_verified: boolean;
      is_developer: boolean;
      ai_processing_consent: boolean;
      ai_redaction_enabled: boolean;
    }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setToken(res.access_token);
    setTokenState(res.access_token);
    setUser({
      id: res.user_id,
      username,
      email: "",
      is_verified: res.is_verified,
      is_developer: res.is_developer,
      ai_processing_consent: res.ai_processing_consent,
      ai_redaction_enabled: res.ai_redaction_enabled,
    });
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

  function logout() {
    setToken(null);
    setTokenState(null);
    setUser(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      login,
      register,
      resendVerification,
      updateAIPrivacy,
      verifyEmail,
      logout,
    }),
    [token, user],
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
