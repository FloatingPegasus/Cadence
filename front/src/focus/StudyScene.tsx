import { useEffect, useState } from "react";

const cats = [
  {
    src: "/focus/cat-keyboard.jpg",
    alt: "Tabby cat sleeping on a keyboard",
  },
  {
    src: "/focus/kitten-sleeping.jpg",
    alt: "Kitten sleeping on its back",
  },
  {
    src: "/focus/tabby-loaf.jpg",
    alt: "Calico kitten napping",
  },
  {
    src: "/focus/window-cat.jpg",
    alt: "Cat looking out a window",
  },
];

export default function StudyScene() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const id = window.setInterval(() => {
      setIndex((current) => (current + 1) % cats.length);
    }, 16000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <button
      type="button"
      className="relative block aspect-[16/9] w-full overflow-hidden border-0 bg-neutral-900 p-0"
      aria-label="Study scene"
      onClick={() => setIndex((current) => (current + 1) % cats.length)}
    >
      {cats.map((cat, photoIndex) => (
        <img
          key={cat.src}
          src={cat.src}
          alt={photoIndex === index ? cat.alt : ""}
          className={
            photoIndex === index
              ? "cadence-fade absolute inset-0 h-full w-full object-cover opacity-100"
              : "cadence-fade absolute inset-0 h-full w-full object-cover opacity-0"
          }
        />
      ))}
    </button>
  );
}
