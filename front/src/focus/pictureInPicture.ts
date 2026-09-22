type PipApi = {
  requestWindow: (options?: {
    width?: number;
    height?: number;
  }) => Promise<Window>;
};

type WebkitVideo = HTMLVideoElement & {
  webkitPresentationMode?: string;
  webkitSetPresentationMode?: (mode: string) => void;
};

export type PipFrame = {
  src: string;
  clock: string;
};

export const PIP_FRAME = { width: 720, height: 405 };

const sceneImages = new Map<string, Promise<HTMLImageElement | null>>();

type LivePip = {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  video: WebkitVideo;
  image: HTMLImageElement | null;
  frame: PipFrame;
  catX: number;
  catDir: number;
  catFrame: number;
  catTick: number;
};

const WALK_SRCS = [1, 2, 3, 4].map(
  (frame) => `/focus/companion-walk-${frame}.png`,
);
const walkSprites: HTMLImageElement[] = [];

let live: LivePip | null = null;
let motion = 0;
let lastPaint = 0;

export function pipApi(): PipApi | null {
  const value = (
    window as Window & { documentPictureInPicture?: PipApi }
  ).documentPictureInPicture;
  return value ?? null;
}

export function pipAvailable(): boolean {
  return pipApi() != null || videoPipAvailable();
}

export function copyPipStyles(target: Document) {
  target.documentElement.className =
    `${document.documentElement.className} cadence-pip`.trim();
  target.documentElement.style.height = "100%";
  target.body.style.margin = "0";
  target.body.style.height = "100%";
  target.body.style.minHeight = "100%";
  target.body.style.overflow = "hidden";
  target.body.style.background = "#111";
  for (const node of document.querySelectorAll(
    'style, link[rel="stylesheet"]',
  )) {
    target.head.appendChild(node.cloneNode(true));
  }
}

export function beginLivePip(frame: PipFrame) {
  const session = ensureLivePip();
  if (!session) return;
  session.frame = frame;
  void loadScene(frame.src).then((image) => {
    if (!live || live.frame.src !== frame.src) return;
    live.image = image;
    paintLive(live);
  });
  paintLive(session);
  void session.video.play().catch(() => {});
}

export function updateLivePip(frame: PipFrame) {
  if (!live) return;
  const srcChanged = live.frame.src !== frame.src;
  live.frame = frame;
  if (srcChanged) {
    live.image = null;
    void loadScene(frame.src).then((image) => {
      if (!live || live.frame.src !== frame.src) return;
      live.image = image;
      paintLive(live);
    });
  }
  paintLive(live);
}

export function presentLivePip(frame: PipFrame): boolean {
  beginLivePip(frame);
  const session = live;
  if (!session) return false;
  const { video } = session;
  try {
    void video.play();
  } catch {
    // Playback can already be running.
  }
  if (typeof video.webkitSetPresentationMode === "function") {
    try {
      video.webkitSetPresentationMode("picture-in-picture");
    } catch {
      // Fall through to the standard call where it exists.
    }
    startMotion();
    if (inPip(video)) {
      video.classList.add("cadence-timer-pip-source-sent");
      return true;
    }
  }
  if (
    typeof video.requestPictureInPicture === "function" &&
    typeof video.webkitSetPresentationMode !== "function"
  ) {
    void video.requestPictureInPicture()
      .then(() => {
        video.classList.add("cadence-timer-pip-source-sent");
        startMotion();
      })
      .catch(() => {});
    startMotion();
    return true;
  }
  return inPip(video);
}

export function isLiveInPip() {
  return live ? inPip(live.video) : false;
}

export function closeLivePip() {
  stopMotion();
  const session = live;
  live = null;
  if (!session) return;
  const stream = session.video.srcObject as MediaStream | null;
  if (stream) {
    for (const track of stream.getTracks()) track.stop();
  }
  session.video.srcObject = null;
  session.video.remove();
}

function ensureLivePip() {
  if (live) return live;
  const canvas = document.createElement("canvas");
  canvas.width = PIP_FRAME.width;
  canvas.height = PIP_FRAME.height;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") return null;
  const stream = canvas.captureStream();
  const video = document.createElement("video") as WebkitVideo;
  video.className = "cadence-timer-pip-source";
  video.muted = true;
  video.defaultMuted = true;
  video.autoplay = true;
  video.playsInline = true;
  video.setAttribute("muted", "");
  video.setAttribute("playsinline", "");
  video.setAttribute("webkit-playsinline", "");
  video.srcObject = stream;
  document.body.appendChild(video);
  loadWalkSprites();
  live = {
    canvas,
    context,
    video,
    image: null,
    frame: { src: "", clock: "" },
    catX: 36,
    catDir: 1,
    catFrame: 0,
    catTick: 0,
  };
  return live;
}

function paintLive(session: LivePip) {
  const { context, canvas, image, frame } = session;
  const drift = 1.04 + 0.04 * Math.sin(performance.now() / 12000);
  context.fillStyle = "#111";
  context.fillRect(0, 0, canvas.width, canvas.height);
  if (image) drawCover(context, image, canvas.width, canvas.height, drift);
  drawCat(session);
  drawClock(context, frame.clock, canvas.height);
  const track = (session.video.srcObject as MediaStream | null)
    ?.getVideoTracks?.()[0] as (MediaStreamTrack & { requestFrame?: () => void }) | undefined;
  track?.requestFrame?.();
}

function startMotion() {
  if (motion) return;
  const tick = (now: number) => {
    motion = requestAnimationFrame(tick);
    if (!live || now - lastPaint < 125) return;
    lastPaint = now;
    stepCat(live, now);
    paintLive(live);
  };
  motion = requestAnimationFrame(tick);
}

function stopMotion() {
  if (!motion) return;
  cancelAnimationFrame(motion);
  motion = 0;
}

function stepCat(session: LivePip, now: number) {
  if (now - session.catTick < 180) return;
  session.catTick = now;
  session.catFrame = (session.catFrame + 1) % walkSprites.length;
  session.catX += session.catDir * 14;
  const limit = session.canvas.width - 120;
  if (session.catX > limit || session.catX < 20) session.catDir *= -1;
}

function loadWalkSprites() {
  if (walkSprites.length > 0) return;
  for (const src of WALK_SRCS) {
    const image = new Image();
    image.src = src;
    walkSprites.push(image);
  }
}

function drawCat(session: LivePip) {
  const sprite = walkSprites[session.catFrame];
  if (!sprite?.complete || !sprite.naturalWidth) return;
  const width = 96;
  const height = 104;
  const y = session.canvas.height - height - 6;
  session.context.save();
  if (session.catDir < 0) {
    session.context.translate(session.catX + width, y);
    session.context.scale(-1, 1);
    session.context.drawImage(sprite, 0, 0, width, height);
  } else {
    session.context.drawImage(sprite, session.catX, y, width, height);
  }
  session.context.restore();
}

function inPip(video: WebkitVideo) {
  return (
    video.webkitPresentationMode === "picture-in-picture" ||
    document.pictureInPictureElement === video
  );
}

function videoPipAvailable(): boolean {
  const canvas = document.createElement("canvas");
  if (typeof canvas.captureStream !== "function") return false;
  const video = document.createElement("video") as WebkitVideo;
  return (
    typeof video.webkitSetPresentationMode === "function" ||
    (typeof video.requestPictureInPicture === "function" &&
      document.pictureInPictureEnabled !== false)
  );
}

function loadScene(src: string): Promise<HTMLImageElement | null> {
  const cached = sceneImages.get(src);
  if (cached) return cached;
  const pending = new Promise<HTMLImageElement | null>((resolve) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
  sceneImages.set(src, pending);
  return pending;
}

function drawCover(
  context: CanvasRenderingContext2D,
  image: HTMLImageElement,
  width: number,
  height: number,
  zoom = 1,
) {
  const scale = Math.max(width / image.width, height / image.height) * zoom;
  const drawnWidth = image.width * scale;
  const drawnHeight = image.height * scale;
  context.drawImage(
    image,
    (width - drawnWidth) / 2,
    (height - drawnHeight) / 2,
    drawnWidth,
    drawnHeight,
  );
}

function drawClock(
  context: CanvasRenderingContext2D,
  clock: string,
  height: number,
) {
  context.font = "500 42px ui-monospace, Menlo, monospace";
  context.fillStyle = "#f6f1e6";
  context.shadowColor = "rgba(18, 24, 18, 0.45)";
  context.shadowBlur = 18;
  context.fillText(clock, 28, height - 36);
  context.shadowBlur = 0;
}
