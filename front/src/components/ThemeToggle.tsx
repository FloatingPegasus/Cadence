import { useTheme } from "../contexts/ThemeContext";

function MoonMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14.8 4.2A8.2 8.2 0 1 0 20 15.4 6.6 6.6 0 0 1 14.8 4.2Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SunMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="3.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M12 3.2v1.6M12 19.2v1.6M3.2 12h1.6M19.2 12h1.6"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = theme === "light" ? "dark" : "light";

  return (
    <button
      type="button"
      aria-label={next === "dark" ? "Dark" : "Light"}
      onClick={() => setTheme(next)}
      className="cadence-chip cadence-chip-icon"
    >
      {next === "dark" ? <MoonMark /> : <SunMark />}
    </button>
  );
}
