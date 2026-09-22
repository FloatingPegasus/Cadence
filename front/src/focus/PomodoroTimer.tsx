import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";

import FocusCat from "./FocusCat";
import { AMBIENCE_OPTIONS, type AmbienceKind } from "./lofi";
import {
  closePreparedPip,
  copyPipStyles,
  openVideoPip,
  PIP_FRAME,
  pipApi,
  pipAvailable,
  presentPreparedPip,
  primeVideoPip,
  type VideoPipSession,
} from "./pictureInPicture";
import { STUDY_SCENES } from "./scenes";
import StudyScene from "./StudyScene";

const MAX_MINUTES = 180;
const EDGE = 16;
const NUDGE = 16;
const MIN_PANEL_W = 300;
const MIN_PANEL_H = 260;

type TimerKind = "pomodoro" | "timer";
type Point = { x: number; y: number };
type Size = { w: number; h: number };
type Box = Point & Size;
type Corner = "nw" | "ne" | "sw" | "se";

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

function clampSize(w: number, h: number, maxW: number, maxH: number): Size {
  return {
    w: Math.min(maxW, Math.max(MIN_PANEL_W, Math.round(w))),
    h: Math.min(maxH, Math.max(MIN_PANEL_H, Math.round(h))),
  };
}

function writeBox(panel: HTMLElement, next: Box) {
  panel.style.left = `${next.x}px`;
  panel.style.top = `${next.y}px`;
  panel.style.width = `${next.w}px`;
  panel.style.height = `${next.h}px`;
  panel.style.maxWidth = "none";
  panel.style.maxHeight = "none";
  panel.style.transform = "none";
  const look = densityFromBox(next.w, next.h);
  panel.dataset.density = look.density;
  if (look.short) panel.setAttribute("data-short", "true");
  else panel.removeAttribute("data-short");
  if (look.tall) panel.setAttribute("data-tall", "true");
  else panel.removeAttribute("data-tall");
}

function followPointer(
  target: HTMLElement,
  pointerId: number,
  onMove: (event: PointerEvent) => void,
  onUp: () => void,
) {
  function move(event: PointerEvent) {
    if (event.pointerId !== pointerId) return;
    event.preventDefault();
    onMove(event);
  }
  function up(event: PointerEvent) {
    if (event.pointerId !== pointerId) return;
    window.removeEventListener("pointermove", move, true);
    window.removeEventListener("pointerup", up, true);
    window.removeEventListener("pointercancel", up, true);
    onUp();
  }
  window.addEventListener("pointermove", move, {
    capture: true,
    passive: false,
  });
  window.addEventListener("pointerup", up, { capture: true });
  window.addEventListener("pointercancel", up, { capture: true });
  try {
    target.setPointerCapture(pointerId);
  } catch {
    // Window listeners still follow the pointer.
  }
}

function ResizeMark({ corner }: { corner: Corner }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`cadence-timer-resize-mark cadence-timer-resize-mark-${corner}`}
      aria-hidden="true"
    >
      <path
        d="M15 7.25 7.25 15M15 11.25 11.25 15"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ResizeHandle({
  corner,
  label,
  onResizeStart,
  onNudge,
}: {
  corner: Corner;
  label: string;
  onResizeStart: (
    event: ReactPointerEvent<HTMLButtonElement>,
    corner: Corner,
  ) => void;
  onNudge: (corner: Corner, dx: number, dy: number) => void;
}) {
  return (
    <button
      type="button"
      data-timer-resize={corner}
      aria-label={label}
      className={`cadence-timer-resize cadence-timer-resize-${corner}`}
      onPointerDown={(event) => {
        if (event.pointerType === "mouse" && event.button > 0) return;
        event.stopPropagation();
        onResizeStart(event, corner);
      }}
      onKeyDown={(event) => {
        const step = event.shiftKey ? NUDGE * 3 : NUDGE;
        let dx = 0;
        let dy = 0;
        if (event.key === "ArrowRight") dx = step;
        else if (event.key === "ArrowLeft") dx = -step;
        else if (event.key === "ArrowDown") dy = step;
        else if (event.key === "ArrowUp") dy = -step;
        else return;
        event.preventDefault();
        onNudge(corner, dx, dy);
      }}
    >
      <ResizeMark corner={corner} />
    </button>
  );
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

function PipMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="3.5"
        y="4.5"
        width="17"
        height="15"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <rect
        x="11.5"
        y="11.5"
        width="8"
        height="7"
        rx="1.2"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
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

function PlayMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M8.2 6.4v11.2L18 12 8.2 6.4Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PauseMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M8 6.5h2.4v11H8V6.5Zm5.6 0H16v11h-2.4V6.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ResetMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M7.2 7.2A6.8 6.8 0 1 1 5.4 12"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M7.2 4.6v3.6H3.8"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MusicMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9.5 18.2V8.1l9-1.6v8.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="7.6" cy="18.2" r="2.2" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="16.1" cy="14.7" r="2.2" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function WaveMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3.6 12c1.6-3.4 3.2-3.4 4.8 0s3.2 3.4 4.8 0 3.2-3.4 4.8 0 3.2 3.4 4.8 0"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TomatoMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 8.2c4.3 0 7.2 2.6 7.2 6.2 0 3.4-3 6.1-7.2 6.1S4.8 17.8 4.8 14.4c0-3.6 2.9-6.2 7.2-6.2Z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M12 8.4c-.2-2 1.1-3.8 3.4-4.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function KindTimerMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-[1.05rem] w-[1.05rem]"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="13" r="7" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M12 13V9.6M12 13l2.6 2.1M9.4 4.8h5.2"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

type TimerDensity = "full" | "icon";

function densityFromBox(width: number, height: number): {
  density: TimerDensity;
  short: boolean;
  tall: boolean;
} {
  if (width < 1) return { density: "full", short: false, tall: false };
  return {
    density: width > 0 && width < 440 ? "icon" : "full",
    short: height > 0 && height < 300,
    tall: height >= 380,
  };
}

interface PomodoroTimerProps {
  sceneIndex: number;
  onCycleScene: () => void;
  playing: boolean;
  ambience: AmbienceKind;
  audioError: string | null;
  onToggleMusic: () => void;
  onChangeAmbience: (kind: AmbienceKind) => void;
  onStatusChange?: (status: { clock: string; running: boolean }) => void;
}

export default function PomodoroTimer({
  sceneIndex,
  onCycleScene,
  playing,
  ambience,
  audioError,
  onToggleMusic,
  onChangeAmbience,
  onStatusChange,
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
  const [pipWindow, setPipWindow] = useState<Window | null>(null);
  const pipWindowRef = useRef<Window | null>(null);
  const videoPipRef = useRef<VideoPipSession | null>(null);
  const [pos, setPos] = useState<Point | null>(null);
  const [size, setSize] = useState<Size | null>(null);
  const sizeRef = useRef<Size | null>(null);
  const [dragging, setDragging] = useState(false);
  const [resizing, setResizing] = useState(false);
  const [density, setDensity] = useState<TimerDensity>("full");
  const [short, setShort] = useState(false);
  const [tall, setTall] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const geometryRef = useRef<Box | null>(null);
  const resizeRef = useRef<{
    pointerId: number;
    corner: Corner;
    x: number;
    y: number;
    w: number;
    h: number;
    originX: number;
    originY: number;
  } | null>(null);

  sizeRef.current = size;

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
      resizeRef.current = null;
      geometryRef.current = null;
      setDragging(false);
      setResizing(false);
      setDensity("full");
      setShort(false);
      setTall(false);
      setPos(null);
      setSize(null);
    }
  }, [expanded]);

  useEffect(() => {
    return () => {
      pipWindowRef.current?.close();
      videoPipRef.current?.close();
      closePreparedPip();
    };
  }, []);

  useEffect(() => {
    const src = STUDY_SCENES[sceneIndex]?.src;
    if (!src) return;
    const frame = { src, clock: formatClock(remaining) };
    videoPipRef.current?.update(frame);
    if (expanded) primeVideoPip(frame);
  }, [sceneIndex, remaining, expanded]);

  useEffect(() => {
    onStatusChange?.({ clock: formatClock(remaining), running });
  }, [remaining, running, onStatusChange]);

  useLayoutEffect(() => {
    if (!expanded) return;
    function syncViewport() {
      const stage = stageRef.current;
      const vv = window.visualViewport;
      if (!stage || !vv) return;
      stage.style.top = `${vv.offsetTop}px`;
      stage.style.left = `${vv.offsetLeft}px`;
      stage.style.right = "auto";
      stage.style.bottom = "auto";
      stage.style.width = `${vv.width}px`;
      stage.style.height = `${vv.height}px`;
    }
    function place(forceCenter: boolean) {
      const stage = stageRef.current;
      const panel = panelRef.current;
      if (!stage || !panel) return;
      syncViewport();
      const bounds = stage.getBoundingClientRect();
      const inset = stageInset(stage);
      const maxW = Math.max(MIN_PANEL_W, bounds.width - inset.left - inset.right);
      const maxH = Math.max(MIN_PANEL_H, bounds.height - inset.top - inset.bottom);
      const live = geometryRef.current;
      const nextSize = live
        ? clampSize(live.w, live.h, maxW, maxH)
        : sizeRef.current
          ? clampSize(sizeRef.current.w, sizeRef.current.h, maxW, maxH)
          : null;
      if (
        !live &&
        nextSize &&
        (!sizeRef.current ||
          nextSize.w !== sizeRef.current.w ||
          nextSize.h !== sizeRef.current.h)
      ) {
        setSize(nextSize);
      }
      const panelW = nextSize?.w ?? panel.offsetWidth;
      const panelH = nextSize?.h ?? panel.offsetHeight;
      if (live) {
        const nextPos = clampPanel(
          forceCenter ? (bounds.width - panelW) / 2 : live.x,
          forceCenter ? (bounds.height - panelH) / 2 : live.y,
          panelW,
          panelH,
          bounds.width,
          bounds.height,
          inset,
        );
        writeBox(panel, { ...nextPos, w: panelW, h: panelH });
        geometryRef.current = { ...nextPos, w: panelW, h: panelH };
        return;
      }
      setPos((current) =>
        clampPanel(
          forceCenter || !current
            ? (bounds.width - panelW) / 2
            : current.x,
          forceCenter || !current
            ? (bounds.height - panelH) / 2
            : current.y,
          panelW,
          panelH,
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
    window.visualViewport?.addEventListener("resize", onResize);
    window.visualViewport?.addEventListener("scroll", onResize);
    const panel = panelRef.current;
    let observer: ResizeObserver | null = null;
    if (panel && typeof ResizeObserver === "function") {
      observer = new ResizeObserver((entries) => {
        if (dragRef.current || resizeRef.current) return;
        const entry = entries[0];
        if (!entry) return;
        const next = densityFromBox(
          entry.contentRect.width,
          entry.contentRect.height,
        );
        setDensity(next.density);
        setShort(next.short);
        setTall(next.tall);
      });
      observer.observe(panel);
    }
    return () => {
      window.removeEventListener("resize", onResize);
      window.visualViewport?.removeEventListener("resize", onResize);
      window.visualViewport?.removeEventListener("scroll", onResize);
      observer?.disconnect();
    };
  }, [expanded]);

  async function openPip() {
    const src = STUDY_SCENES[sceneIndex]?.src;
    if (!src) return;
    const api = pipApi();
    try {
      if (api) {
        const next = await api.requestWindow(PIP_FRAME);
        copyPipStyles(next.document);
        next.addEventListener("pagehide", () => {
          pipWindowRef.current = null;
          setPipWindow(null);
        });
        pipWindowRef.current?.close();
        videoPipRef.current?.close();
        videoPipRef.current = null;
        pipWindowRef.current = next;
        setPipWindow(next);
        setExpanded(false);
        return;
      }
      if (presentPreparedPip()) {
        setExpanded(false);
        return;
      }
      videoPipRef.current?.close();
      videoPipRef.current = await openVideoPip({
        src,
        clock: formatClock(remaining),
      });
      setExpanded(false);
    } catch {
      // The browser may reject Picture-in-Picture without a user gesture.
    }
  }

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
    const live = geometryRef.current;
    if (!drag || !stage || !panel || !live) return;
    const bounds = stage.getBoundingClientRect();
    const next = clampPanel(
      clientX - bounds.left - drag.offsetX,
      clientY - bounds.top - drag.offsetY,
      live.w,
      live.h,
      bounds.width,
      bounds.height,
      stageInset(stage),
    );
    rememberBox({ ...next, w: live.w, h: live.h });
  }

  function beginDrag(event: ReactPointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse" && event.button > 0) return;
    const stage = stageRef.current;
    const panel = panelRef.current;
    if (!stage || !panel) return;
    const stageBox = stage.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - box.left,
      offsetY: event.clientY - box.top,
    };
    rememberBox({
      x: box.left - stageBox.left,
      y: box.top - stageBox.top,
      w: size?.w ?? box.width,
      h: size?.h ?? box.height,
    });
    setDragging(true);
    followPointer(
      event.currentTarget,
      event.pointerId,
      (moveEvent) => {
        if (!dragRef.current) return;
        moveTo(moveEvent.clientX, moveEvent.clientY);
      },
      finishGesture,
    );
    event.preventDefault();
  }

  function applyResize(
    corner: Corner,
    start: { x: number; y: number; w: number; h: number },
    dx: number,
    dy: number,
  ) {
    const stage = stageRef.current;
    if (!stage) return;
    const bounds = stage.getBoundingClientRect();
    const inset = stageInset(stage);
    const maxW = Math.max(MIN_PANEL_W, bounds.width - inset.left - inset.right);
    const maxH = Math.max(MIN_PANEL_H, bounds.height - inset.top - inset.bottom);
    let w = start.w;
    let h = start.h;
    let x = start.x;
    let y = start.y;
    if (corner === "ne" || corner === "se") w = start.w + dx;
    if (corner === "nw" || corner === "sw") w = start.w - dx;
    if (corner === "sw" || corner === "se") h = start.h + dy;
    if (corner === "nw" || corner === "ne") h = start.h - dy;
    const next = clampSize(w, h, maxW, maxH);
    if (corner === "nw" || corner === "sw") x = start.x + start.w - next.w;
    if (corner === "nw" || corner === "ne") y = start.y + start.h - next.h;
    const point = clampPanel(x, y, next.w, next.h, bounds.width, bounds.height, inset);
    rememberBox({ ...point, w: next.w, h: next.h });
  }

  function panelBox() {
    const stage = stageRef.current;
    const panel = panelRef.current;
    if (!stage || !panel) return null;
    const stageBox = stage.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    return {
      x: pos?.x ?? box.left - stageBox.left,
      y: pos?.y ?? box.top - stageBox.top,
      w: size?.w ?? box.width,
      h: size?.h ?? box.height,
    };
  }

  function beginResize(
    event: ReactPointerEvent<HTMLElement>,
    corner: Corner,
  ) {
    const start = panelBox();
    if (!start) return;
    resizeRef.current = {
      pointerId: event.pointerId,
      corner,
      ...start,
      originX: event.clientX,
      originY: event.clientY,
    };
    rememberBox(start);
    setResizing(true);
    followPointer(
      event.currentTarget,
      event.pointerId,
      (moveEvent) => {
        const current = resizeRef.current;
        if (!current) return;
        applyResize(
          current.corner,
          current,
          moveEvent.clientX - current.originX,
          moveEvent.clientY - current.originY,
        );
      },
      finishGesture,
    );
    event.preventDefault();
  }

  function rememberBox(next: Box) {
    const panel = panelRef.current;
    geometryRef.current = next;
    if (panel) writeBox(panel, next);
  }

  function finishGesture() {
    const next = geometryRef.current;
    dragRef.current = null;
    resizeRef.current = null;
    geometryRef.current = null;
    if (next) {
      const look = densityFromBox(next.w, next.h);
      setPos({ x: next.x, y: next.y });
      setSize({ w: next.w, h: next.h });
      setDensity(look.density);
      setShort(look.short);
      setTall(look.tall);
    }
    setDragging(false);
    setResizing(false);
  }

  function nudgeSize(corner: Corner, dx: number, dy: number) {
    const start = panelBox();
    if (!start) return;
    applyResize(corner, start, dx, dy);
    const next = geometryRef.current;
    if (!next) return;
    geometryRef.current = null;
    const look = densityFromBox(next.w, next.h);
    setPos({ x: next.x, y: next.y });
    setSize({ w: next.w, h: next.h });
    setDensity(look.density);
    setShort(look.short);
    setTall(look.tall);
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
        size?.w ?? panel.offsetWidth,
        size?.h ?? panel.offsetHeight,
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
    const startLabel = running ? "Pause" : "Start";
    return (
      <div className="cadence-timer-controls-wrap">
        <div className="cadence-timer-controls">
          <button
            type="button"
            aria-label={startLabel}
            onClick={() => setRunning((value) => !value)}
            className="cadence-chip cadence-chip-solid cadence-timer-action"
          >
            <span className="cadence-timer-action-mark">
              {running ? <PauseMark /> : <PlayMark />}
            </span>
            <span className="cadence-timer-action-label">{startLabel}</span>
          </button>
          <button
            type="button"
            aria-label="Reset"
            onClick={reset}
            className="cadence-chip cadence-timer-action"
          >
            <span className="cadence-timer-action-mark">
              <ResetMark />
            </span>
            <span className="cadence-timer-action-label">Reset</span>
          </button>
          <div className="cadence-timer-kind">
            <span className="cadence-timer-kind-mark" aria-hidden="true">
              {kind === "pomodoro" ? <TomatoMark /> : <KindTimerMark />}
            </span>
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
          </div>
          <div className="cadence-timer-minutes flex shrink-0 items-center gap-2">
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
                  className="cadence-chip cadence-chip-count cadence-timer-minutes-spacer"
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

  const liveBox = geometryRef.current;
  const look = liveBox
    ? densityFromBox(liveBox.w, liveBox.h)
    : { density, short, tall };

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
              dragging || resizing
                ? "cadence-timer-scene pointer-events-none absolute inset-0"
                : "cadence-timer-scene absolute inset-0"
            }
          >
            <StudyScene
              variant="stage"
              index={sceneIndex}
              onCycle={onCycleScene}
            />
            <FocusCat running={running} />
          </div>
          <div
            ref={panelRef}
            className={[
              "cadence-timer-float",
              dragging ? "cadence-timer-float-dragging" : "",
              resizing ? "cadence-timer-float-resizing" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            data-density={look.density}
            data-short={look.short ? "true" : undefined}
            data-tall={look.tall ? "true" : undefined}
            style={
              geometryRef.current
                ? {
                    left: geometryRef.current.x,
                    top: geometryRef.current.y,
                    width: geometryRef.current.w,
                    height: geometryRef.current.h,
                    maxWidth: "none",
                    maxHeight: "none",
                    transform: "none",
                  }
                : pos
                  ? {
                      left: pos.x,
                      top: pos.y,
                      ...(size
                        ? {
                            width: size.w,
                            height: size.h,
                            maxWidth: "none",
                            maxHeight: "none",
                          }
                        : {}),
                    }
                  : {
                      left: "50%",
                      top: "50%",
                      transform: "translate(-50%, -50%)",
                    }
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
            <ResizeHandle
              corner="nw"
              label="Resize from top left"
              onResizeStart={beginResize}
              onNudge={nudgeSize}
            />
            <ResizeHandle
              corner="ne"
              label="Resize from top right"
              onResizeStart={beginResize}
              onNudge={nudgeSize}
            />
            <ResizeHandle
              corner="sw"
              label="Resize from bottom left"
              onResizeStart={beginResize}
              onNudge={nudgeSize}
            />
            <ResizeHandle
              corner="se"
              label="Resize from bottom right"
              onResizeStart={beginResize}
              onNudge={nudgeSize}
            />
            <div className="cadence-timer-float-body">
            <div className="cadence-timer-head">
              <p className="cadence-timer-mode">{label}</p>
              <div className="cadence-timer-head-actions">
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
                {pipAvailable() ? (
                  <button
                    type="button"
                    aria-label="Picture in picture"
                    onClick={() => void openPip()}
                    className="cadence-chip cadence-chip-icon"
                  >
                    <PipMark />
                  </button>
                ) : null}
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
            <p className="cadence-timer-float-clock">{clock}</p>
            {renderControls()}
            <div className="cadence-timer-music-row">
              <button
                type="button"
                aria-label={playing ? "Pause music" : "Play lo-fi"}
                onClick={onToggleMusic}
                className="cadence-chip cadence-chip-accent cadence-timer-action cadence-timer-music"
              >
                <span className="cadence-timer-action-mark">
                  <MusicMark />
                </span>
                <span className="cadence-timer-action-label">
                  {playing ? "Pause music" : "Play lo-fi"}
                </span>
              </button>
              <div className="cadence-timer-kind cadence-timer-ambience">
                <span className="cadence-timer-kind-mark" aria-hidden="true">
                  <WaveMark />
                </span>
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
            </div>
            <p
              className="cadence-timer-status"
              role={audioError ? "alert" : undefined}
            >
              {audioError ?? "\u00a0"}
            </p>
            </div>
          </div>
        </div>,
        document.body,
      )}
      {pipWindow
        ? createPortal(
            <div className="cadence-timer-pip">
              <StudyScene
                variant="stage"
                index={sceneIndex}
                onCycle={onCycleScene}
              />
              <p className="cadence-timer-pip-clock">{clock}</p>
            </div>,
            pipWindow.document.body,
          )
        : null}
    </>
  );
}
