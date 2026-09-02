import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

const CAT_W = 81;
const CAT_H = 87;
const DRAG_PX = 8;
const WALK_FRAME_MS = 200;
const WALK_STEP = 1.05;
const MIN_ROAM = 7;

const WALK_FRAMES = [
  "/focus/companion-walk-1.png",
  "/focus/companion-walk-2.png",
  "/focus/companion-walk-3.png",
  "/focus/companion-walk-4.png",
];

type Pose = "sleep" | "sit" | "walk" | "pet";
type Facing = "left" | "right";

export interface FocusCatProps {
  clock: string;
  running: boolean;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function reducedMotion() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function catLabel(pose: Pose, running: boolean, clock: string) {
  if (running) return `Cat, ${clock}`;
  if (pose === "sleep") return "Cat, sleeping";
  if (pose === "pet") return "Cat, purring";
  if (pose === "walk") return "Cat, roaming";
  return "Cat, sitting";
}

function stepToward(
  from: { x: number; y: number },
  to: { x: number; y: number },
  step: number,
) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.hypot(dx, dy);
  if (dist <= step) return { x: to.x, y: to.y };
  return {
    x: from.x + (dx / dist) * step,
    y: from.y + (dy / dist) * step,
  };
}

function roamSpot(
  host: HTMLElement,
  running: boolean,
): { x: number; y: number } {
  const { width, height } = host.getBoundingClientRect();
  const maxX = Math.max(4, 100 * (1 - CAT_W / Math.max(width, 1)) - 4);
  const maxY = Math.max(4, 100 * (1 - CAT_H / Math.max(height, 1)) - 4);
  const y = 5 + Math.random() * Math.min(12, Math.max(0, maxY - 5));
  if (running) {
    return Math.random() < 0.5
      ? { x: 4 + Math.random() * Math.min(16, maxX - 4), y }
      : { x: Math.max(4, maxX - 16) + Math.random() * Math.min(16, maxX - 4), y };
  }
  return { x: 4 + Math.random() * Math.max(0, maxX - 4), y };
}

function pointerToPercent(
  host: HTMLElement,
  cat: HTMLElement,
  clientX: number,
  clientY: number,
  offsetX: number,
  offsetY: number,
) {
  const bounds = host.getBoundingClientRect();
  const width = cat.offsetWidth || CAT_W;
  const height = cat.offsetHeight || CAT_H;
  const left = clamp(clientX - bounds.left - offsetX, 0, Math.max(0, bounds.width - width));
  const top = clamp(clientY - bounds.top - offsetY, 0, Math.max(0, bounds.height - height));
  const bottom = clamp(bounds.height - top - height, 0, Math.max(0, bounds.height - height));
  return {
    x: bounds.width === 0 ? 0 : (100 * left) / bounds.width,
    y: bounds.height === 0 ? 0 : (100 * bottom) / bounds.height,
  };
}

function Heart() {
  return (
    <svg viewBox="0 0 12 10" className="cadence-cat-heart" aria-hidden="true">
      <path
        d="M6 9.2C2.2 6.4.8 4.6.8 3.1.8 1.7 1.9.7 3.2.7c.8 0 1.5.4 1.8.9h.2c.4-.5 1-.9 1.8-.9 1.3 0 2.4 1 2.4 2.4 0 1.5-1.4 3.3-5.2 6.1Z"
        fill="currentColor"
      />
    </svg>
  );
}

function catSrc(pose: Pose, walkFrame: number) {
  if (pose === "walk") return WALK_FRAMES[walkFrame] ?? WALK_FRAMES[0];
  if (pose === "sleep") return "/focus/companion-sleep.png";
  return "/focus/companion-sit.png";
}

export default function FocusCat({ clock, running }: FocusCatProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const catRef = useRef<HTMLButtonElement>(null);
  const posRef = useRef({ x: 8, y: 8 });
  const runningRef = useRef(running);
  const skipClick = useRef(false);
  const dragRef = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const petTimer = useRef(0);
  const poseRef = useRef<Pose>("sleep");
  const walkingRef = useRef(false);
  const [pose, setPose] = useState<Pose>("sleep");
  const [facing, setFacing] = useState<Facing>("right");
  const [pos, setPos] = useState({ x: 8, y: 8 });
  const [walkFrame, setWalkFrame] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [visible, setVisible] = useState(true);
  const [pageVisible, setPageVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState !== "hidden",
  );

  runningRef.current = running;
  posRef.current = pos;
  poseRef.current = pose;

  useEffect(() => {
    for (const src of WALK_FRAMES) {
      const img = new Image();
      img.src = src;
    }
  }, []);

  useEffect(() => {
    const node = hostRef.current;
    if (!node || typeof IntersectionObserver !== "function") return;
    const observer = new IntersectionObserver((entries) => {
      setVisible(entries.some((entry) => entry.isIntersecting));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    function onVis() {
      setPageVisible(document.visibilityState !== "hidden");
    }
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    if (!running) return;
    setPose((current) => (current === "pet" ? current : "sit"));
  }, [running]);

  useEffect(() => {
    if (running) return;
    const id = window.setTimeout(() => {
      setPose((current) => (current === "pet" || current === "walk" ? current : "sleep"));
    }, 5000);
    return () => window.clearTimeout(id);
  }, [running]);

  useEffect(() => {
    if (reducedMotion() || !visible || !pageVisible || dragging) return;
    let cancelled = false;
    let waitId = 0;
    let stepId = 0;
    const target = { x: posRef.current.x, y: posRef.current.y };

    function restThenSchedule() {
      walkingRef.current = false;
      setWalkFrame(0);
      setPose((current) => {
        if (current === "pet") return current;
        return runningRef.current ? "sit" : "sleep";
      });
      schedule();
    }

    function tick() {
      if (cancelled) return;
      if (poseRef.current === "pet") {
        stepId = window.setTimeout(tick, WALK_FRAME_MS);
        return;
      }
      setWalkFrame((frame) => (frame + 1) % WALK_FRAMES.length);
      const next = stepToward(posRef.current, target, WALK_STEP);
      setPos(next);
      if (next.x === target.x && next.y === target.y) {
        restThenSchedule();
        return;
      }
      stepId = window.setTimeout(tick, WALK_FRAME_MS);
    }

    function startWalk() {
      if (cancelled) return;
      const host = hostRef.current;
      if (!host || poseRef.current === "pet") {
        schedule();
        return;
      }
      const next = roamSpot(host, runningRef.current);
      const dist = Math.hypot(next.x - posRef.current.x, next.y - posRef.current.y);
      if (dist < MIN_ROAM) {
        schedule();
        return;
      }
      target.x = next.x;
      target.y = next.y;
      setFacing(next.x >= posRef.current.x ? "right" : "left");
      setWalkFrame(0);
      walkingRef.current = true;
      setPose("walk");
      stepId = window.setTimeout(tick, WALK_FRAME_MS);
    }

    function schedule() {
      const wait = runningRef.current
        ? 16000 + Math.random() * 9000
        : 8000 + Math.random() * 7000;
      waitId = window.setTimeout(startWalk, wait);
    }

    schedule();
    return () => {
      cancelled = true;
      walkingRef.current = false;
      window.clearTimeout(waitId);
      window.clearTimeout(stepId);
    };
  }, [visible, pageVisible, dragging, running]);

  useEffect(() => {
    return () => window.clearTimeout(petTimer.current);
  }, []);

  function pet() {
    window.clearTimeout(petTimer.current);
    setPose("pet");
    petTimer.current = window.setTimeout(() => {
      if (walkingRef.current) {
        setPose("walk");
        return;
      }
      setPose(runningRef.current ? "sit" : "sleep");
    }, 1600);
  }

  function onPointerDown(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.stopPropagation();
    const cat = event.currentTarget;
    const box = cat.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - box.left,
      offsetY: event.clientY - box.top,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    cat.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event: ReactPointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    const host = hostRef.current;
    if (!drag || !host || event.pointerId !== drag.pointerId) return;
    const distance = Math.hypot(
      event.clientX - drag.startX,
      event.clientY - drag.startY,
    );
    if (!drag.moved && distance < DRAG_PX) return;
    drag.moved = true;
    setDragging(true);
    setPose((current) => (current === "sleep" ? "sit" : current));
    setPos(
      pointerToPercent(
        host,
        event.currentTarget,
        event.clientX,
        event.clientY,
        drag.offsetX,
        drag.offsetY,
      ),
    );
  }

  function onPointerUp(event: ReactPointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (drag.moved) skipClick.current = true;
    dragRef.current = null;
    setDragging(false);
  }

  function onClick(event: ReactMouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    if (skipClick.current) {
      skipClick.current = false;
      return;
    }
    pet();
  }

  return (
    <div ref={hostRef} className="cadence-focus-cat-stage">
      <button
        ref={catRef}
        type="button"
        draggable={false}
        aria-label={catLabel(pose, running, clock)}
        data-pose={pose}
        data-dragging={dragging ? "true" : undefined}
        className="cadence-focus-cat"
        style={{
          left: `${pos.x}%`,
          bottom: `${pos.y}%`,
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={onClick}
        onKeyDown={(event) => event.stopPropagation()}
      >
        {running ? (
          <span className="cadence-focus-cat-clock" aria-hidden="true">
            {clock}
          </span>
        ) : null}
        {pose === "sleep" && !running ? (
          <span className="cadence-cat-zzz" aria-hidden="true">
            z
          </span>
        ) : null}
        {pose === "pet" ? (
          <span className="cadence-cat-hearts" aria-hidden="true">
            <Heart />
            <Heart />
            <Heart />
          </span>
        ) : null}
        <span className="cadence-focus-cat-motion">
          <span
            className="cadence-cat-figure"
            data-pose={pose}
            data-facing={pose === "walk" ? facing : "right"}
          >
            <img
              src={catSrc(pose, walkFrame)}
              alt=""
              draggable={false}
              className="cadence-cat-sprite"
            />
          </span>
        </span>
      </button>
    </div>
  );
}
