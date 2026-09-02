import { useEffect, useState } from "react";

export interface StudyScenePhoto {
  src: string;
  alt: string;
}

export const STUDY_SCENES: StudyScenePhoto[] = [
  { src: "/focus/cat-keyboard.jpg", alt: "Tabby cat sleeping on a keyboard" },
  { src: "/focus/kittens-heart.jpg", alt: "Kittens sleeping in a heart shape" },
  { src: "/focus/kitten-slipper.jpg", alt: "Kitten sitting in a slipper" },
  { src: "/focus/window-cat.jpg", alt: "Cat looking out a window" },
  { src: "/focus/kitten-yawn.jpg", alt: "Ginger kitten yawning" },
  { src: "/focus/cat-box.jpg", alt: "Cat sitting in a cardboard box" },
  { src: "/focus/tabby-loaf.jpg", alt: "Calico kitten napping" },
  { src: "/focus/snuggly-kittens.jpg", alt: "Tabby kittens snuggled together" },
  { src: "/focus/kitten-piano.jpg", alt: "Kitten on a piano" },
  { src: "/focus/kitten-sleeping.jpg", alt: "Kitten sleeping on its back" },
  { src: "/focus/napping-kitten.jpg", alt: "Kitten napping on a blanket" },
  { src: "/focus/cat-sunny.jpg", alt: "Cat in a sunny patch" },
  { src: "/focus/lawn-kitten.jpg", alt: "Kitten on a lawn looking at flowers" },
  { src: "/focus/kitten-blanket.jpg", alt: "Kitten in a pink blanket" },
  { src: "/focus/sunday-kitty.jpg", alt: "Fluffy cat in warm light" },
  { src: "/focus/mellow-kitten.jpg", alt: "Grey tabby kitten looking up" },
  { src: "/focus/cat-couch.jpg", alt: "Cat resting on a couch" },
  { src: "/focus/two-sleepy.jpg", alt: "Two sleepy cats" },
  { src: "/focus/curious-kitten.jpg", alt: "Curious kitten with a leaf" },
  { src: "/focus/kitten-plaid.jpg", alt: "Kitten hiding under a plaid" },
  { src: "/focus/cat-yawn.jpg", alt: "Cat sitting and yawning" },
  { src: "/focus/litter-kittens.jpg", alt: "Litter of kittens in the grass" },
  { src: "/focus/white-kitten.jpg", alt: "White kitten" },
  { src: "/focus/tabby-city.jpg", alt: "Tabby cat in a city window" },
  { src: "/focus/siamese.jpg", alt: "Siamese cat" },
  { src: "/focus/focused-kitten.jpg", alt: "Kitten looking away" },
  { src: "/focus/cat-sky.jpg", alt: "Cat looking at the sky" },
  { src: "/focus/grey-sleeping.jpg", alt: "Grey cat sleeping" },
  { src: "/focus/kitten-mommy.jpg", alt: "Kitten playing with its mother" },
  { src: "/focus/innocent-kitten.jpg", alt: "Kitten looking at the camera" },
];

export function useStudyScene() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const id = window.setInterval(() => {
      setIndex((current) => (current + 1) % STUDY_SCENES.length);
    }, 24000);
    return () => window.clearInterval(id);
  }, []);

  function cycle() {
    setIndex((current) => (current + 1) % STUDY_SCENES.length);
  }

  return { index, cycle };
}
