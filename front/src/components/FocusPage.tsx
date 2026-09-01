import { useEffect, useRef, useState } from "react";

import {
  AMBIENCE_OPTIONS,
  LofiEngine,
  type AmbienceKind,
} from "../focus/lofi";
import PomodoroTimer from "../focus/PomodoroTimer";
import { useStudyScene } from "../focus/scenes";
import StudyScene from "../focus/StudyScene";

export default function FocusPage() {
  const engine = useRef<LofiEngine | null>(null);
  const { index: sceneIndex, cycle: cycleScene } = useStudyScene();
  const [playing, setPlaying] = useState(false);
  const [ambience, setAmbience] = useState<AmbienceKind>("off");
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
      player.setAmbience(ambience);
      setPlaying(true);
    } catch {
      setAudioError("Could not start audio in this browser.");
    }
  }

  function changeAmbience(kind: AmbienceKind) {
    setAmbience(kind);
    engine.current?.setAmbience(kind);
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
          <select
            aria-label="Background noise"
            value={ambience}
            onChange={(event) =>
              changeAmbience(event.target.value as AmbienceKind)
            }
            className="cadence-chip cadence-chip-select cadence-chip-select-wide"
          >
            {AMBIENCE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {audioError && (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {audioError}
        </p>
      )}
      <div className="mt-10 overflow-hidden rounded-3xl shadow-[var(--shadow-page)]">
        <StudyScene index={sceneIndex} onCycle={cycleScene} />
      </div>
      <div className="cadence-surface mt-6">
        <PomodoroTimer
          sceneIndex={sceneIndex}
          onCycleScene={cycleScene}
          playing={playing}
          ambience={ambience}
          audioError={audioError}
          onToggleMusic={() => void toggleMusic()}
          onChangeAmbience={changeAmbience}
        />
      </div>
    </div>
  );
}
