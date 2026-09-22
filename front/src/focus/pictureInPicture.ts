type PipApi = {
  requestWindow: (options?: {
    width?: number;
    height?: number;
  }) => Promise<Window>;
};

type WebkitVideo = HTMLVideoElement & {
  webkitPresentationMode?: string;
  webkitSupportsPresentationMode?: (mode: string) => boolean;
  webkitSetPresentationMode?: (mode: string) => void;
};

export type PipFrame = {
  src: string;
  clock: string;
};

export type VideoPipSession = {
  update: (frame: PipFrame) => void;
  close: () => void;
};

export const PIP_FRAME = { width: 720, height: 405 };

const sceneImages = new Map<string, Promise<HTMLImageElement | null>>();

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

export async function openVideoPip(frame: PipFrame): Promise<VideoPipSession> {
  const canvas = document.createElement("canvas");
  canvas.width = PIP_FRAME.width;
  canvas.height = PIP_FRAME.height;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") {
    throw new Error("Picture in picture is unavailable");
  }

  let current = frame;
  let image: HTMLImageElement | null = null;
  let closed = false;

  const paint = () => {
    context.fillStyle = "#111";
    context.fillRect(0, 0, canvas.width, canvas.height);
    if (image) drawCover(context, image, canvas.width, canvas.height);
    drawClock(context, current.clock, canvas.height);
  };

  const show = (src: string) => {
    void loadScene(src).then((next) => {
      if (closed || current.src !== src) return;
      image = next;
      paint();
    });
  };

  paint();
  const video = document.createElement("video");
  const webkit = video as WebkitVideo;
  video.className = "cadence-timer-pip-source";
  video.muted = true;
  video.autoplay = true;
  video.playsInline = true;
  video.setAttribute("playsinline", "");
  video.srcObject = canvas.captureStream(15);
  document.body.appendChild(video);

  const close = () => {
    if (closed) return;
    closed = true;
    video.removeEventListener("leavepictureinpicture", close);
    video.removeEventListener("webkitpresentationmodechanged", onWebkitMode);
    const stream = video.srcObject as { getTracks?: () => Array<{ stop: () => void }> } | null;
    if (stream && typeof stream.getTracks === "function") {
      for (const track of stream.getTracks()) track.stop();
    }
    video.srcObject = null;
    video.remove();
  };

  const onWebkitMode = () => {
    if (webkit.webkitPresentationMode !== "picture-in-picture") close();
  };

  try {
    await video.play();
    if (typeof video.requestPictureInPicture === "function") {
      await video.requestPictureInPicture();
    } else if (typeof webkit.webkitSetPresentationMode === "function") {
      webkit.webkitSetPresentationMode("picture-in-picture");
    } else {
      throw new Error("Picture in picture is unavailable");
    }
  } catch (error) {
    close();
    throw error;
  }
  video.addEventListener("leavepictureinpicture", close);
  video.addEventListener("webkitpresentationmodechanged", onWebkitMode);
  show(current.src);

  return {
    update(next) {
      if (closed) return;
      const srcChanged = next.src !== current.src;
      current = next;
      if (srcChanged) {
        image = null;
        show(next.src);
      }
      paint();
    },
    close,
  };
}

function videoPipAvailable(): boolean {
  const canvas = document.createElement("canvas");
  if (typeof canvas.captureStream !== "function") return false;
  const video = document.createElement("video") as WebkitVideo;
  if (
    typeof video.requestPictureInPicture === "function" &&
    document.pictureInPictureEnabled !== false
  ) {
    return true;
  }
  return video.webkitSupportsPresentationMode?.("picture-in-picture") === true;
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
) {
  const scale = Math.max(width / image.width, height / image.height);
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
