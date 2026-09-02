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
      {STUDY_SCENES.map((cat, photoIndex) => (
        <img
          key={cat.src}
          src={cat.src}
          alt={photoIndex === index ? cat.alt : ""}
          className={[
            "cadence-scene-crossfade cadence-scene-drift absolute inset-0 h-full w-full object-cover",
            photoIndex === index ? "z-[1] opacity-100" : "z-0 opacity-0",
          ].join(" ")}
        />
      ))}
    </button>
  );
}
