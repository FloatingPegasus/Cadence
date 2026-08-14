import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

function Header() {
  const { user, logout } = useAuth();
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function handleLogout() {
    setLogoutError(null);
    try {
      await logout();
    } catch (error) {
      setLogoutError(
        error instanceof Error ? error.message : "Could not log out",
      );
    }
  }

  return (
    <header className="mb-6 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-semibold text-neutral-100 tracking-tight">
          Cadence
        </h1>
        <p className="text-sm text-neutral-500 mt-1">
          Your daily record
        </p>
      </div>
      {user && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-400">{user.username}</span>
          {logoutError && (
            <span role="alert" className="text-xs text-red-400">
              {logoutError}
            </span>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
          >
            Log out
          </button>
        </div>
      )}
    </header>
  );
}

export default Header;
