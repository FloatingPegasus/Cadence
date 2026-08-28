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

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setRemaining((current) => {
        if (current > 1) return current - 1;
        const nextMode = mode === "work" ? "break" : "work";
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
    <div>
      <p className="text-sm text-neutral-500">
        {mode === "work" ? "Work" : "Break"}
      </p>
      <p className="mt-3 font-mono text-5xl tracking-tight text-neutral-100">
        {formatClock(remaining)}
      </p>
      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={() => setRunning((value) => !value)}
          className="cadence-chip cadence-chip-accent"
        >
          {running ? "Pause" : "Start"}
        </button>
        <button
          type="button"
          onClick={reset}
          className="cadence-chip"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
