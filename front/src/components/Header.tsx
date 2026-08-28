import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

function Header() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
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
    <header className="mb-10 flex items-baseline justify-between gap-4">
      <h1 className="cadence-mark text-[1.35rem] font-medium text-neutral-100">
        Cadence
      </h1>
      {user && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            className="cadence-chip"
          >
            {theme === "light" ? "Dark" : "Light"}
          </button>
          <span className="text-sm text-neutral-500">{user.username}</span>
          {logoutError && (
            <span role="alert" className="text-xs text-red-400">
              {logoutError}
            </span>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="cadence-chip"
          >
            Log out
          </button>
        </div>
      )}
    </header>
  );
}

export default Header;
