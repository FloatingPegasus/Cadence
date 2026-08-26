import { useEffect, useRef, useState } from "react";

import { LofiEngine } from "../focus/lofi";
import PomodoroTimer from "../focus/PomodoroTimer";
import StudyScene from "../focus/StudyScene";

export default function FocusPage() {
  const engine = useRef<LofiEngine | null>(null);
  const [playing, setPlaying] = useState(false);
  const [rain, setRain] = useState(true);
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
        engine.current = new LofiEngine();
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
    <div className="cadence-enter">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-base font-medium text-neutral-100">Focus</h1>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void toggleMusic()}
            className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-100 transition-colors duration-200 hover:bg-neutral-700"
          >
            {playing ? "Pause music" : "Play lo-fi"}
          </button>
          <button
            type="button"
            onClick={toggleRain}
            className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition-colors duration-200 hover:bg-neutral-900"
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
      <div className="mt-6 overflow-hidden rounded-2xl border border-neutral-800">
        <StudyScene />
      </div>
      <div className="mt-6 max-w-sm">
        <PomodoroTimer />
      </div>
    </div>
  );
}
