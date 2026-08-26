import { useEffect, useState } from "react";
import { request } from "../api";

function VerifyPage() {
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Verifying your email...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("No verification token found in the URL.");
      return;
    }
    // Keep the one-time credential out of browser history and future referrer
    // headers after capturing it for the API request.
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.hash}`,
    );

    request<{ is_verified: boolean }>("/api/auth/verify", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then((res) => {
        if (res.is_verified) {
          setStatus("success");
          setMessage("Your email has been verified! You can now log in.");
        } else {
          setStatus("success");
          setMessage("Account verified successfully.");
        }
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Verification failed.");
      });
  }, []);

  return (
    <div className="max-w-sm mx-auto px-6 py-20 text-center">
      <h1 className="text-xl font-semibold text-neutral-100 tracking-tight mb-2">
        Cadence
      </h1>
      <p className="text-sm text-neutral-500 mb-4">
        Habits, an hourly log, and a quiet focus room.
      </p>

      {status === "loading" && (
        <p className="text-sm text-neutral-400">{message}</p>
      )}

      {status === "success" && (
        <div className="space-y-4">
          <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3">
            <p className="text-sm text-neutral-300">{message}</p>
          </div>
          <a
            href="/"
            className="inline-block px-4 py-2 rounded-lg bg-neutral-800 text-sm font-medium text-neutral-100 hover:bg-neutral-700 transition-colors"
          >
            Go to login
          </a>
        </div>
      )}

      {status === "error" && (
        <div className="space-y-4">
          <div className="rounded-lg border border-red-800 bg-red-900/20 px-4 py-3">
            <p className="text-sm text-red-400">{message}</p>
          </div>
          <a
            href="/"
            className="inline-block px-4 py-2 rounded-lg bg-neutral-800 text-sm font-medium text-neutral-100 hover:bg-neutral-700 transition-colors"
          >
            Back to login
          </a>
        </div>
      )}
    </div>
  );
}

export default VerifyPage;
