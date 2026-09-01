import { useAuth } from "../contexts/AuthContext";
import ThemeToggle from "./ThemeToggle";

function Header() {
  const { user } = useAuth();

  return (
    <header className="mb-6 flex items-center justify-between gap-3 sm:mb-10">
      <h1 className="cadence-mark min-w-0 text-[1.35rem] font-medium text-neutral-100">
        Cadence
      </h1>
      {user && (
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <ThemeToggle />
          <span className="hidden text-sm text-neutral-500 sm:inline">
            {user.username}
          </span>
        </div>
      )}
    </header>
  );
}

export default Header;
