import { useEffect, useRef, useState } from "react";

import { LofiEngine } from "../focus/lofi";
import PomodoroTimer from "../focus/PomodoroTimer";
import StudyScene from "../focus/StudyScene";

export default function FocusPage() {
  const engine = useRef<LofiEngine | null>(null);
  const [playing, setPlaying] = useState(false);
  const [rain, setRain] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);

  useEffect(() => {
    engine.current = new LofiEngine();
    return () => engine.current?.stop();
  }, []);

  async function toggleMusic() {
    const player = engine.current;
    if (!player) return;
    setAudioError(null);
    try {
      if (player.isPlaying) {
        player.stop();
        setPlaying(false);
        return;
      }
      await player.start();
      player.setRain(rain);
      setPlaying(true);
    } catch {
      setAudioError("Could not start audio in this browser.");
    }
  }

  function toggleRain() {
    const next = !rain;
    setRain(next);
    engine.current?.setRain(next);
  }

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="cadence-title text-2xl font-medium text-neutral-100">
          Focus
        </h1>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void toggleMusic()}
            className="cadence-chip cadence-chip-accent"
          >
            {playing ? "Pause music" : "Play lo-fi"}
          </button>
          <button
            type="button"
            onClick={toggleRain}
            className="cadence-chip"
          >
            {rain ? "Rain on" : "Rain off"}
          </button>
        </div>
      </div>
      {audioError && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {audioError}
        </p>
      )}
      <div className="mt-10 overflow-hidden rounded-3xl shadow-[var(--shadow-page)]">
        <StudyScene />
      </div>
      <div className="cadence-surface mt-6">
        <PomodoroTimer />
      </div>
    </div>
  );
}
