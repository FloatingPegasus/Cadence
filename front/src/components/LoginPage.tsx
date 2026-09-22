import { useState, type FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";

interface LoginPageProps {
  intent?: "login" | "claim";
  headingId?: string;
  onFinished?: () => void;
}

function LoginPage({
  intent = "login",
  headingId,
  onFinished,
}: LoginPageProps) {
  const { login, register, claim, resendVerification } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register" | "resend" | "claim">(
    intent === "claim" ? "claim" : "login",
  );
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sentAgain, setSentAgain] = useState(false);

  const checkEmail = Boolean(successMsg) && (mode === "register" || mode === "resend");
  const mailInServerLog = Boolean(successMsg?.includes("server log"));
  const title =
    mode === "claim" ? "Keep this" : mode === "register" ? "Register" : "Cadence";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSentAgain(false);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
        onFinished?.();
      } else if (mode === "claim") {
        await claim(username, email, password);
        onFinished?.();
      } else if (mode === "register") {
        await register(username, email, password);
        onFinished?.();
      } else {
        setSuccessMsg(await resendVerification(email));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendAgain() {
    setError(null);
    setLoading(true);
    try {
      setSuccessMsg(await resendVerification(email));
      setSentAgain(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const brand = checkEmail || title === "Cadence";

  return (
    <div className="cadence-surface">
      <h1
        id={headingId}
        className={`${brand ? "cadence-mark cadence-wordmark" : "cadence-title"} text-center text-xl text-neutral-100 ${checkEmail ? "mb-6" : "mb-8"}`}
      >
        {checkEmail ? "Cadence" : title}
      </h1>

      {successMsg ? (
        <div className="text-center space-y-4">
          <h2 className="cadence-title text-lg font-semibold tracking-tight text-neutral-100">
            {mailInServerLog ? "Account created" : "Check your email"}
          </h2>
          <p className="text-sm text-neutral-400 break-words">
            {mailInServerLog
              ? successMsg
              : email
                ? `Link sent to ${email}.`
                : successMsg}
          </p>
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          {email && !mailInServerLog ? (
            <button
              type="button"
              onClick={() => void handleSendAgain()}
              disabled={loading}
              className="cadence-chip cadence-chip-solid w-full"
            >
              {loading ? "Please wait..." : sentAgain ? "Sent again" : "Send again"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setSuccessMsg(null);
              setSentAgain(false);
              setError(null);
              setMode("login");
            }}
            className="w-full min-h-11 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Back to login
          </button>
        </div>
      ) : (
        <>
          <form onSubmit={handleSubmit} className="space-y-4">
            {mode !== "resend" && (
              <div>
                <label
                  htmlFor="auth-username"
                  className="block text-xs text-neutral-500 mb-1.5"
                >
                  {mode === "login" ? "Username or email" : "Username"}
                </label>
                <input
                  id="auth-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  className="cadence-field"
                  placeholder={
                    mode === "login" ? "you@example.com" : "your name"
                  }
                  required
                />
              </div>
            )}

            {mode !== "login" && (
              <div>
              <label
                htmlFor="auth-email"
                className="block text-xs text-neutral-500 mb-1.5"
              >
                Email
              </label>
              <input
                id="auth-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                className="cadence-field"
                placeholder="you@example.com"
                  required
                />
              </div>
            )}

            {mode !== "resend" && (
              <div>
                <label
                  htmlFor="auth-password"
                  className="block text-xs text-neutral-500 mb-1.5"
                >
                  Password
                </label>
                <input
                  id="auth-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  className="cadence-field"
                  placeholder="••••••"
                  minLength={mode === "login" ? undefined : 8}
                  required
                />
              </div>
            )}

            {error ? <p className="text-sm text-red-400">{error}</p> : null}

            <button
              type="submit"
              disabled={loading}
              className="cadence-chip cadence-chip-solid w-full"
            >
              {loading
                ? "Please wait..."
                : mode === "login"
                  ? "Log in"
                  : mode === "claim"
                    ? "Keep this"
                    : mode === "register"
                      ? "Register"
                      : "Resend verification"}
            </button>
          </form>

          {mode !== "claim" ? (
            <div className="mt-4 space-y-2">
              {mode === "login" ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("register");
                      setError(null);
                    }}
                    className="w-full min-h-11 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
                  >
                    Need an account? Register
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMode("resend");
                      setError(null);
                    }}
                    className="w-full min-h-11 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
                  >
                    Resend verification email
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError(null);
                  }}
                  className="w-full min-h-11 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
                >
                  Back to login
                </button>
              )}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

export default LoginPage;
