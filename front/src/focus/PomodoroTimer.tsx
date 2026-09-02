import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";

import { AMBIENCE_OPTIONS, type AmbienceKind } from "./lofi";
import StudyScene from "./StudyScene";

const MAX_MINUTES = 180;
const EDGE = 16;
const NUDGE = 16;

type TimerKind = "pomodoro" | "timer";
type Point = { x: number; y: number };

type StageInset = { top: number; right: number; bottom: number; left: number };

function readPx(styles: CSSStyleDeclaration, name: string) {
  const value = parseFloat(styles.getPropertyValue(name));
  return Number.isFinite(value) ? value : 0;
}

function stageInset(stage: HTMLElement): StageInset {
  const styles = getComputedStyle(stage);
  return {
    top: EDGE + readPx(styles, "--timer-safe-top"),
    right: EDGE + readPx(styles, "--timer-safe-right"),
    bottom: EDGE + readPx(styles, "--timer-safe-bottom"),
    left: EDGE + readPx(styles, "--timer-safe-left"),
  };
}

function clampPanel(
  x: number,
  y: number,
  panelW: number,
  panelH: number,
  stageW: number,
  stageH: number,
  inset: StageInset = {
    top: EDGE,
    right: EDGE,
    bottom: EDGE,
    left: EDGE,
  },
): Point {
  const maxX = stageW - panelW - inset.right;
  const maxY = stageH - panelH - inset.bottom;
  return {
    x:
      maxX < inset.left
        ? Math.max(0, (stageW - panelW) / 2)
        : Math.min(maxX, Math.max(inset.left, x)),
    y:
      maxY < inset.top
        ? Math.max(0, (stageH - panelH) / 2)
        : Math.min(maxY, Math.max(inset.top, y)),
  };
}

function ignoreDragFrom(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  if (target.closest("[data-timer-drag]")) return false;
  return Boolean(target.closest("button, input, select, textarea, a"));
}

function clampMinutes(value: number) {
  if (!Number.isFinite(value)) return 1;
  return Math.min(MAX_MINUTES, Math.max(1, Math.round(value)));
}

function parseMinutes(draft: string) {
  const trimmed = draft.trim();
  if (trimmed === "") return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 1) return null;
  return clampMinutes(value);
}

function MinutesInput({
  draft,
  disabled,
  label,
  invalid,
  onDraftChange,
  onCommit,
}: {
  draft: string;
  disabled: boolean;
  label: string;
  invalid: boolean;
  onDraftChange: (draft: string) => void;
  onCommit: (draft: string) => void;
}) {
  return (
    <input
      type="text"
      inputMode="numeric"
      pattern="[0-9]*"
      disabled={disabled}
      aria-label={label}
      aria-invalid={invalid}
      value={draft}
      onChange={(event) => onDraftChange(event.target.value.replace(/\D/g, ""))}
      onBlur={(event) => onCommit(event.currentTarget.value)}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        onCommit(event.currentTarget.value);
        event.currentTarget.blur();
      }}
      className="cadence-chip cadence-chip-count"
    />
  );
}

function formatClock(total: number) {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function ExpandMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9 4H4v5M15 4h5v5M4 15v5h5M20 15v5h-5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CollapseMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M4 9h5V4M20 9h-5V4M4 15h5v5M20 15h-5v5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MoveMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 4v16M4 12h16M12 4l-2.4 2.4M12 4l2.4 2.4M12 20l-2.4-2.4M12 20l2.4-2.4M4 12l2.4-2.4M4 12l2.4 2.4M20 12l-2.4-2.4M20 12l-2.4 2.4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface PomodoroTimerProps {
  sceneIndex: number;
  onCycleScene: () => void;
  playing: boolean;
  ambience: AmbienceKind;
  audioError: string | null;
  onToggleMusic: () => void;
  onChangeAmbience: (kind: AmbienceKind) => void;
}

export default function PomodoroTimer({
  sceneIndex,
  onCycleScene,
  playing,
  ambience,
  audioError,
  onToggleMusic,
  onChangeAmbience,
}: PomodoroTimerProps) {
  const [kind, setKind] = useState<TimerKind>("pomodoro");
  const [mode, setMode] = useState<"work" | "break">("work");
  const [workMinutes, setWorkMinutes] = useState(25);
  const [breakMinutes, setBreakMinutes] = useState(5);
  const [timerMinutes, setTimerMinutes] = useState(25);
  const [workDraft, setWorkDraft] = useState("25");
  const [breakDraft, setBreakDraft] = useState("5");
  const [timerDraft, setTimerDraft] = useState("25");
  const [minutesError, setMinutesError] = useState<"work" | "break" | "timer" | null>(
    null,
  );
  const [remaining, setRemaining] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [pos, setPos] = useState<Point | null>(null);
  const [dragging, setDragging] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setRemaining((current) => {
        if (current > 1) return current - 1;
        if (kind === "timer") {
          setRunning(false);
          return 0;
        }
        const nextMode = mode === "work" ? "break" : "work";
        setMode(nextMode);
        return (nextMode === "work" ? workMinutes : breakMinutes) * 60;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, mode, kind, workMinutes, breakMinutes]);

  useEffect(() => {
    if (!expanded) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setExpanded(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  useEffect(() => {
    if (!expanded) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [expanded]);

  useEffect(() => {
    if (!expanded) {
      dragRef.current = null;
      setDragging(false);
      setPos(null);
    }
  }, [expanded]);

  useLayoutEffect(() => {
    if (!expanded) return;
    function place(forceCenter: boolean) {
      const stage = stageRef.current;
      const panel = panelRef.current;
      if (!stage || !panel) return;
      const bounds = stage.getBoundingClientRect();
      const inset = stageInset(stage);
      setPos((current) =>
        clampPanel(
          forceCenter || !current
            ? (bounds.width - panel.offsetWidth) / 2
            : current.x,
          forceCenter || !current
            ? (bounds.height - panel.offsetHeight) / 2
            : current.y,
          panel.offsetWidth,
          panel.offsetHeight,
          bounds.width,
          bounds.height,
          inset,
        ),
      );
    }
    place(true);
    function onResize() {
      place(false);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [expanded]);

  function applyKind(next: TimerKind) {
    setKind(next);
    setMode("work");
    setRunning(false);
    setRemaining((next === "pomodoro" ? workMinutes : timerMinutes) * 60);
  }

  function changeWorkMinutes(minutes: number) {
    setWorkMinutes(minutes);
    if (!running && kind === "pomodoro" && mode === "work") {
      setRemaining(minutes * 60);
    }
  }

  function changeBreakMinutes(minutes: number) {
    setBreakMinutes(minutes);
    if (!running && kind === "pomodoro" && mode === "break") {
      setRemaining(minutes * 60);
    }
  }

  function changeTimerMinutes(minutes: number) {
    setTimerMinutes(minutes);
    if (!running && kind === "timer") {
      setRemaining(minutes * 60);
    }
  }

  function commitMinutes(
    field: "work" | "break" | "timer",
    draft: string,
    committed: number,
    setDraft: (next: string) => void,
    apply: (minutes: number) => void,
  ) {
    const minutes = parseMinutes(draft);
    if (minutes == null) {
      setMinutesError(field);
      setDraft(String(committed));
      return;
    }
    setMinutesError(null);
    setDraft(String(minutes));
    apply(minutes);
  }

  function reset() {
    setRunning(false);
    setMode("work");
    setRemaining((kind === "pomodoro" ? workMinutes : timerMinutes) * 60);
  }

  function moveTo(clientX: number, clientY: number) {
    const drag = dragRef.current;
    const stage = stageRef.current;
    const panel = panelRef.current;
    if (!drag || !stage || !panel) return;
    const bounds = stage.getBoundingClientRect();
    setPos(
      clampPanel(
        clientX - bounds.left - drag.offsetX,
        clientY - bounds.top - drag.offsetY,
        panel.offsetWidth,
        panel.offsetHeight,
        bounds.width,
        bounds.height,
        stageInset(stage),
      ),
    );
  }

  function endDrag() {
    dragRef.current = null;
    setDragging(false);
  }

  function beginDrag(event: ReactPointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse" && event.button > 0) return;
    const stage = stageRef.current;
    const panel = panelRef.current;
    if (!stage || !panel) return;
    const stageBox = stage.getBoundingClientRect();
    const panelBox = panel.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - panelBox.left,
      offsetY: event.clientY - panelBox.top,
    };
    setPos({
      x: panelBox.left - stageBox.left,
      y: panelBox.top - stageBox.top,
    });
    setDragging(true);

    function onMove(moveEvent: PointerEvent | MouseEvent) {
      if (!dragRef.current) return;
      moveEvent.preventDefault();
      moveTo(moveEvent.clientX, moveEvent.clientY);
    }

    function onUp() {
      window.removeEventListener("pointermove", onMove, true);
      window.removeEventListener("mousemove", onMove, true);
      window.removeEventListener("pointerup", onUp, true);
      window.removeEventListener("pointercancel", onUp, true);
      window.removeEventListener("mouseup", onUp, true);
      endDrag();
    }

    window.addEventListener("pointermove", onMove, {
      capture: true,
      passive: false,
    });
    window.addEventListener("mousemove", onMove, { capture: true });
    window.addEventListener("pointerup", onUp, { capture: true });
    window.addEventListener("pointercancel", onUp, { capture: true });
    window.addEventListener("mouseup", onUp, { capture: true });

    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Window listeners still follow the pointer.
    }
    event.preventDefault();
  }

  function nudge(dx: number, dy: number) {
    const stage = stageRef.current;
    const panel = panelRef.current;
    if (!stage || !panel) return;
    const bounds = stage.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    const current = pos ?? {
      x: box.left - bounds.left,
      y: box.top - bounds.top,
    };
    setPos(
      clampPanel(
        current.x + dx,
        current.y + dy,
        panel.offsetWidth,
        panel.offsetHeight,
        bounds.width,
        bounds.height,
        stageInset(stage),
      ),
    );
  }

  const label =
    kind === "timer" ? "Timer" : mode === "work" ? "Work" : "Break";
  const clock = formatClock(remaining);

  function renderControls() {
    return (
      <div className="mt-6">
        <div className="cadence-timer-controls flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setRunning((value) => !value)}
            className="cadence-chip cadence-chip-accent"
          >
            {running ? "Pause" : "Start"}
          </button>
          <button type="button" onClick={reset} className="cadence-chip">
            Reset
          </button>
          <select
            aria-label="Timer"
            value={kind}
            disabled={running}
            onChange={(event) => applyKind(event.target.value as TimerKind)}
            className="cadence-chip cadence-chip-select"
          >
            <option value="pomodoro">Pomodoro</option>
            <option value="timer">Timer</option>
          </select>
          <div className="flex shrink-0 items-center gap-2">
            {kind === "pomodoro" ? (
              <>
                <MinutesInput
                  draft={workDraft}
                  disabled={running}
                  label="Work minutes"
                  invalid={minutesError === "work"}
                  onDraftChange={(next) => {
                    setMinutesError(null);
                    setWorkDraft(next);
                  }}
                  onCommit={(draft) =>
                    commitMinutes(
                      "work",
                      draft,
                      workMinutes,
                      setWorkDraft,
                      changeWorkMinutes,
                    )
                  }
                />
                <MinutesInput
                  draft={breakDraft}
                  disabled={running}
                  label="Break minutes"
                  invalid={minutesError === "break"}
                  onDraftChange={(next) => {
                    setMinutesError(null);
                    setBreakDraft(next);
                  }}
                  onCommit={(draft) =>
                    commitMinutes(
                      "break",
                      draft,
                      breakMinutes,
                      setBreakDraft,
                      changeBreakMinutes,
                    )
                  }
                />
              </>
            ) : (
              <>
                <MinutesInput
                  draft={timerDraft}
                  disabled={running}
                  label="Minutes"
                  invalid={minutesError === "timer"}
                  onDraftChange={(next) => {
                    setMinutesError(null);
                    setTimerDraft(next);
                  }}
                  onCommit={(draft) =>
                    commitMinutes(
                      "timer",
                      draft,
                      timerMinutes,
                      setTimerDraft,
                      changeTimerMinutes,
                    )
                  }
                />
                <span
                  aria-hidden="true"
                  className="cadence-chip cadence-chip-count invisible"
                >
                  00
                </span>
              </>
            )}
          </div>
        </div>
        <p
          className="cadence-timer-status"
          role={minutesError ? "alert" : undefined}
        >
          {minutesError ? "Enter minutes" : "\u00a0"}
        </p>
      </div>
    );
  }

  return (
    <>
      <div>
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-neutral-500">{label}</p>
          <button
            type="button"
            aria-label="Full screen"
            onClick={() => setExpanded(true)}
            className="cadence-chip cadence-chip-icon"
          >
            <ExpandMark />
          </button>
        </div>
        <p className="mt-3 font-mono text-5xl tracking-tight text-neutral-100">
          {clock}
        </p>
        {renderControls()}
      </div>
      {expanded &&
        createPortal(
          <div
            ref={stageRef}
            className="cadence-timer-stage"
            role="dialog"
            aria-label="Timer"
          >
          <div
            className={
              dragging
                ? "pointer-events-none absolute inset-0"
                : "absolute inset-0"
            }
          >
            <StudyScene
              variant="stage"
              index={sceneIndex}
              onCycle={onCycleScene}
            />
          </div>
          <div
            ref={panelRef}
            className={
              dragging
                ? "cadence-timer-float cadence-timer-float-dragging"
                : "cadence-timer-float"
            }
            style={
              pos
                ? { left: pos.x, top: pos.y }
                : { left: "50%", top: "50%", transform: "translate(-50%, -50%)" }
            }
            onPointerDown={(event) => {
              if (ignoreDragFrom(event.target)) return;
              beginDrag(event);
            }}
            onPointerMove={(event) => {
              if (!dragRef.current) return;
              moveTo(event.clientX, event.clientY);
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm text-neutral-300">{label}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  data-timer-drag
                  aria-label="Move timer"
                  className="cadence-chip cadence-chip-icon cadence-timer-drag"
                  onPointerDown={(event) => {
                    event.stopPropagation();
                    beginDrag(event);
                  }}
                  onKeyDown={(event) => {
                    const step = event.shiftKey ? NUDGE * 3 : NUDGE;
                    if (event.key === "ArrowLeft") nudge(-step, 0);
                    else if (event.key === "ArrowRight") nudge(step, 0);
                    else if (event.key === "ArrowUp") nudge(0, -step);
                    else if (event.key === "ArrowDown") nudge(0, step);
                    else return;
                    event.preventDefault();
                  }}
                >
                  <MoveMark />
                </button>
                <button
                  type="button"
                  aria-label="Exit full screen"
                  onClick={() => setExpanded(false)}
                  className="cadence-chip cadence-chip-icon"
                >
                  <CollapseMark />
                </button>
              </div>
            </div>
            <p className="mt-3 font-mono text-6xl tracking-tight text-neutral-50 sm:text-7xl">
              {clock}
            </p>
            {renderControls()}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onToggleMusic}
                className="cadence-chip cadence-chip-accent cadence-timer-music"
              >
                {playing ? "Pause music" : "Play lo-fi"}
              </button>
              <select
                aria-label="Background noise"
                value={ambience}
                onChange={(event) =>
                  onChangeAmbience(event.target.value as AmbienceKind)
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
            <p
              className="cadence-timer-status"
              role={audioError ? "alert" : undefined}
            >
              {audioError ?? "\u00a0"}
            </p>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
