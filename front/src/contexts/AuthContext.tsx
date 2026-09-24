import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  request,
  setWriteSessionGate,
  updateAIPreferences,
  type AIPreferences,
} from "../api";

export type AuthDialog = "login" | "claim" | null;

export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  is_verified: boolean;
  is_guest: boolean;
  is_developer: boolean;
  ai_processing_consent: boolean;
  ai_redaction_enabled: boolean;
}

interface RegisterResult {
  id: number;
  username: string;
  email: string | null;
  is_verified: boolean;
  is_guest: boolean;
  message: string;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  allowGuests: boolean;
  aiEnabled: boolean;
  authDialog: AuthDialog;
  login: (identifier: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<RegisterResult>;
  claim: (username: string, email: string, password: string) => Promise<void>;
  ensureSession: () => Promise<AuthUser>;
  openLogin: () => void;
  openClaim: () => void;
  closeAuth: () => void;
  resendVerification: (email: string) => Promise<string>;
  updateAIPrivacy: (
    processingConsent: boolean,
    redactionEnabled: boolean,
  ) => Promise<AIPreferences>;
  verifyEmail: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>("/api/auth/me", { method: "GET" });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [allowGuests, setAllowGuests] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [authDialog, setAuthDialog] = useState<AuthDialog>(null);
  const userRef = useRef<AuthUser | null>(null);
  const allowGuestsRef = useRef(false);
  const minting = useRef<Promise<AuthUser> | null>(null);

  userRef.current = user;
  allowGuestsRef.current = allowGuests;

  const openLogin = useCallback(() => setAuthDialog("login"), []);
  const openClaim = useCallback(() => setAuthDialog("claim"), []);
  const closeAuth = useCallback(() => setAuthDialog(null), []);

  const ensureSession = useCallback(async () => {
    if (userRef.current) return userRef.current;
    if (minting.current) return minting.current;
    minting.current = (async () => {
      if (!allowGuestsRef.current) {
        openLogin();
        throw new Error("Log in");
      }
      await request("/api/auth/guest", { method: "POST" });
      const next = await fetchMe();
      userRef.current = next;
      setUser(next);
      return next;
    })();
    try {
      return await minting.current;
    } finally {
      minting.current = null;
    }
  }, [openLogin]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      request<AuthUser>("/api/auth/me", { method: "GET" }).catch(() => null),
      request<{ allow_guests: boolean; ai_enabled: boolean }>(
        "/api/auth/options",
        { method: "GET" },
      ).catch(() => ({ allow_guests: false, ai_enabled: false })),
    ])
      .then(([session, options]) => {
        if (cancelled) return;
        setUser(session);
        userRef.current = session;
        setAllowGuests(options.allow_guests);
        allowGuestsRef.current = options.allow_guests;
        setAiEnabled(options.ai_enabled);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setWriteSessionGate(() => ensureSession().then(() => undefined));
    return () => setWriteSessionGate(null);
  }, [ensureSession]);

  async function login(identifier: string, password: string) {
    await request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: identifier, password }),
    });
    const next = await fetchMe();
    userRef.current = next;
    setUser(next);
    setIsLoading(false);
    setAuthDialog(null);
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
    const next = await fetchMe();
    userRef.current = next;
    setUser(next);
    setAuthDialog(null);
    return res;
  }

  async function claim(username: string, email: string, password: string) {
    await request("/api/auth/claim", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    const next = await fetchMe();
    userRef.current = next;
    setUser(next);
    setAuthDialog(null);
  }

  async function verifyEmail(verifyToken: string) {
    await request<{
      id: number;
      username: string;
      email: string | null;
      is_verified: boolean;
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
    userRef.current = null;
    setUser(null);
    setIsLoading(false);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      allowGuests,
      aiEnabled,
      authDialog,
      login,
      register,
      claim,
      ensureSession,
      openLogin,
      openClaim,
      closeAuth,
      resendVerification,
      updateAIPrivacy,
      verifyEmail,
      logout,
    }),
    [
      user,
      isLoading,
      allowGuests,
      aiEnabled,
      authDialog,
      ensureSession,
      openLogin,
      openClaim,
      closeAuth,
    ],
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
