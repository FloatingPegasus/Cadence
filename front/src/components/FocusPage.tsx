import { useEffect, useRef, useState } from "react";

import FocusCat from "../focus/FocusCat";
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
  const [timer, setTimer] = useState({ clock: "25:00", running: false });

  useEffect(() => {
    engine.current = new LofiEngine();
    return () => engine.current?.dispose();
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
      await player.setAmbience(ambience);
      setPlaying(true);
    } catch {
      setAudioError("Could not start audio in this browser.");
    }
  }

  function changeAmbience(kind: AmbienceKind) {
    setAmbience(kind);
    setAudioError(null);
    void engine.current?.setAmbience(kind).catch(() => {
      setAudioError("Could not start audio in this browser.");
    });
  }

  return (
    <div>
      <div>
        <h1 className="cadence-title text-2xl font-medium text-neutral-100">
          Focus
        </h1>
        <div className="mt-4 flex flex-wrap gap-2">
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
      <div className="cadence-polaroid mt-8">
        <div className="relative overflow-hidden rounded-[0.28rem]">
          <StudyScene index={sceneIndex} onCycle={cycleScene} />
          <FocusCat running={timer.running} />
        </div>
      </div>
      <div className="cadence-surface cadence-surface-quiet mt-6">
        <PomodoroTimer
          sceneIndex={sceneIndex}
          onCycleScene={cycleScene}
          playing={playing}
          ambience={ambience}
          audioError={audioError}
          onToggleMusic={() => void toggleMusic()}
          onChangeAmbience={changeAmbience}
          onStatusChange={setTimer}
        />
      </div>
    </div>
  );
}
