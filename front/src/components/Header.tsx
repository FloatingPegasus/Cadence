import { useId, useRef, useEffect } from "react";

import { useAuth } from "../contexts/AuthContext";
import ThemeToggle from "./ThemeToggle";
import LoginPage from "./LoginPage";

function SettingsMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M4 8h8.5M17.5 8H20M4 16h2.5M11.5 16H20"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <circle cx="15" cy="8" r="2.3" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="9" cy="16" r="2.3" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

interface HeaderProps {
  settingsOpen: boolean;
  onOpenSettings: () => void;
}

function Header({ settingsOpen, onOpenSettings }: HeaderProps) {
  const { user, authDialog, openLogin, openClaim, closeAuth } = useAuth();
  const headingId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!authDialog) return;
    const previous = document.activeElement;
    dialogRef.current?.focus();
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeAuth();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = originalOverflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, [authDialog, closeAuth]);

  return (
    <header className="mb-5 flex items-center justify-between gap-3 sm:mb-8">
      <h1 className="cadence-mark cadence-wordmark min-w-0 text-[1.7rem] text-neutral-100">
        Cadence
      </h1>
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <ThemeToggle />
        <button
          type="button"
          aria-label="Settings"
          aria-current={settingsOpen ? "page" : undefined}
          onClick={onOpenSettings}
          className={
            settingsOpen
              ? "cadence-chip cadence-chip-icon text-neutral-100"
              : "cadence-chip cadence-chip-icon cadence-chip-ghost"
          }
        >
          <SettingsMark />
        </button>
        {user?.is_guest ? (
          <button type="button" onClick={openClaim} className="cadence-chip cadence-chip-solid">
            Keep this
          </button>
        ) : user ? (
          <span className="hidden text-sm text-neutral-500 sm:inline">
            {user.username}
          </span>
        ) : (
          <button type="button" onClick={openLogin} className="cadence-chip cadence-chip-solid">
            Log in
          </button>
        )}
      </div>
      {authDialog ? (
        <div
          className="cadence-overlay fixed inset-0 z-50 flex items-center justify-center bg-neutral-50/35 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeAuth();
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={headingId}
            tabIndex={-1}
            className="cadence-dialog w-full max-w-sm outline-none"
          >
            <LoginPage
              headingId={headingId}
              intent={authDialog}
              onFinished={closeAuth}
            />
          </div>
        </div>
      ) : null}
    </header>
  );
}

export default Header;
