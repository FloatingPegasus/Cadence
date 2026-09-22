type PipApi = {
  requestWindow: (options?: {
    width?: number;
    height?: number;
  }) => Promise<Window>;
};

export const PIP_FRAME = { width: 720, height: 405 };

export function pipApi(): PipApi | null {
  const value = (
    window as Window & { documentPictureInPicture?: PipApi }
  ).documentPictureInPicture;
  return value ?? null;
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
