import { useLayoutEffect, useRef, type ReactNode } from "react";

interface ViewPaneProps {
  active: boolean;
  children: ReactNode;
}

export default function ViewPane({ active, children }: ViewPaneProps) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node || !active) return;
    node.classList.remove("cadence-enter");
    void node.offsetWidth;
    node.classList.add("cadence-enter");
  }, [active]);

  return (
    <div
      ref={ref}
      hidden={!active}
      aria-hidden={!active}
      {...(!active ? { inert: "" } : {})}
    >
      {children}
    </div>
  );
}
