import { useEffect, useState } from "react";

const WORK_SECONDS = 25 * 60;
const BREAK_SECONDS = 5 * 60;

function formatClock(total: number) {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export default function PomodoroTimer() {
  const [mode, setMode] = useState<"work" | "break">("work");
  const [remaining, setRemaining] = useState(WORK_SECONDS);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(0);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setRemaining((current) => {
        if (current > 1) return current - 1;
        const nextMode = mode === "work" ? "break" : "work";
        if (mode === "work") setCompleted((count) => count + 1);
        setMode(nextMode);
        return nextMode === "work" ? WORK_SECONDS : BREAK_SECONDS;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, mode]);

  function reset() {
    setRunning(false);
    setMode("work");
    setRemaining(WORK_SECONDS);
  }

  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-950/70 px-5 py-4">
      <p className="text-xs uppercase tracking-wider text-neutral-500">
        {mode === "work" ? "Focus" : "Break"}
      </p>
      <p className="mt-2 font-mono text-4xl tracking-tight text-neutral-100">
        {formatClock(remaining)}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setRunning((value) => !value)}
          className="rounded-lg bg-violet-500 px-3 py-1.5 text-xs text-white transition-colors duration-200 hover:bg-violet-400"
        >
          {running ? "Pause" : "Start"}
        </button>
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition-colors duration-200 hover:bg-neutral-900"
        >
          Reset
        </button>
      </div>
      <p className="mt-3 text-xs text-neutral-600">
        {completed} session{completed === 1 ? "" : "s"} today
      </p>
    </div>
  );
}
