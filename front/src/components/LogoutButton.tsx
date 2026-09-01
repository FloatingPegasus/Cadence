import { useState } from "react";

import { useAuth } from "../contexts/AuthContext";

function LogoutButton() {
  const { logout } = useAuth();
  const [error, setError] = useState<string | null>(null);

  async function handleLogout() {
    setError(null);
    try {
      await logout();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not log out",
      );
    }
  }

  return (
    <div>
      <button type="button" onClick={handleLogout} className="cadence-chip">
        Log out
      </button>
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}

export default LogoutButton;
