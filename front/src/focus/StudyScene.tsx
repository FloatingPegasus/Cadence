import { useEffect, useRef, useState } from "react";

import { STUDY_SCENES } from "./scenes";

interface StudySceneProps {
  index: number;
  onCycle: () => void;
  variant?: "card" | "stage";
}

export default function StudyScene({
  index,
  onCycle,
  variant = "card",
}: StudySceneProps) {
  const stage = variant === "stage";
  const currentRef = useRef(index);
  const [outgoing, setOutgoing] = useState(index);

  useEffect(() => {
    if (currentRef.current === index) return;
    setOutgoing(currentRef.current);
    currentRef.current = index;
  }, [index]);

  const frames =
    outgoing === index
      ? [index]
      : [outgoing, index];

  return (
    <button
      type="button"
      className={
        stage
          ? "absolute inset-0 block overflow-hidden border-0 bg-neutral-900 p-0"
          : "relative block aspect-[16/9] w-full overflow-hidden border-0 bg-neutral-900 p-0"
      }
      aria-label="Study scene"
      onClick={onCycle}
    >
      {frames.map((photoIndex) => {
        const cat = STUDY_SCENES[photoIndex];
        if (!cat) return null;
        const current = photoIndex === index;
        return (
          <img
            key={cat.src}
            src={cat.src}
            alt={current ? cat.alt : ""}
            className={[
              "cadence-scene-crossfade absolute inset-0 h-full w-full object-cover",
              current
                ? "cadence-scene-drift z-[1] opacity-100"
                : "z-0 opacity-0",
            ].join(" ")}
          />
        );
      })}
    </button>
  );
}
