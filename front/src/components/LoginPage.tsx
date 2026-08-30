import { useState, type FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

function LoginPage() {
  const { login, register, resendVerification } = useAuth();
  const { theme, setTheme } = useTheme();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register" | "resend">("login");
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sentAgain, setSentAgain] = useState(false);

  const checkEmail = Boolean(successMsg) && (mode === "register" || mode === "resend");
  const mailInServerLog = Boolean(successMsg?.includes("server log"));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSentAgain(false);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else if (mode === "register") {
        const res = await register(username, email, password);
        setSuccessMsg(
          res.message ||
            "Account created. Check your email to verify before logging in.",
        );
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

  return (
    <div className="px-6 py-6">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          className="cadence-chip"
        >
          {theme === "light" ? "Dark" : "Light"}
        </button>
      </div>
      <div className="cadence-surface mx-auto mt-10 max-w-sm">
      <h1 className={`cadence-mark text-center text-xl font-semibold tracking-tight text-neutral-100 ${checkEmail ? "mb-6" : "mb-2"}`}>
        Cadence
      </h1>
      {!checkEmail ? (
        <p className="mb-8 text-center text-sm text-neutral-500">
          Habits, hours, and a focus room.
        </p>
      ) : null}

      {successMsg ? (
        <div className="text-center space-y-4">
          <h2 className="cadence-mark text-lg font-semibold tracking-tight text-neutral-100">
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
              className="w-full min-h-11 px-4 py-2.5 rounded-lg bg-neutral-800 text-sm font-medium text-neutral-100 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
                  className="w-full min-h-11 px-3 py-2.5 rounded-lg border border-neutral-800 bg-neutral-900 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
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
                className="w-full min-h-11 px-3 py-2.5 rounded-lg border border-neutral-800 bg-neutral-900 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
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
                  className="w-full min-h-11 px-3 py-2.5 rounded-lg border border-neutral-800 bg-neutral-900 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
                  placeholder="••••••"
                  required
                />
              </div>
            )}

            {error && <p className="text-sm text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full min-h-11 px-4 py-2.5 rounded-lg bg-neutral-800 text-sm font-medium text-neutral-100 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? "Please wait..."
                : mode === "login"
                  ? "Log in"
                  : mode === "register"
                    ? "Register"
                    : "Resend verification"}
            </button>
          </form>

          <div className="mt-4 space-y-2">
            {mode === "login" ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setMode("register");
                    setError(null);
                  }}
                  className="w-full text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
                >
                  Need an account? Register
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode("resend");
                    setError(null);
                  }}
                  className="w-full text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
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
                className="w-full text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                Back to login
              </button>
            )}
          </div>
        </>
      )}
      </div>
    </div>
  );
}

export default LoginPage;
