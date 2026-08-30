interface MonthNavProps {
  month: string;
  onChange: (month: string) => void;
}

function MonthNav({ month, onChange }: MonthNavProps) {
  function go(delta: number) {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    onChange(
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    );
  }

  const label = new Date(month + "-01").toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
  });

  return (
    <div className="mb-8 flex items-center justify-center gap-3 sm:mb-10 sm:items-baseline">
      <button
        type="button"
        aria-label="Previous month"
        onClick={() => go(-1)}
        className="cadence-chip"
      >
        ←
      </button>
      <h1 className="cadence-title min-w-0 flex-1 text-center text-xl font-medium text-neutral-100 sm:w-44 sm:flex-none sm:text-2xl">
        {label}
      </h1>
      <button
        type="button"
        aria-label="Next month"
        onClick={() => go(1)}
        className="cadence-chip"
      >
        →
      </button>
    </div>
  );
}

export default MonthNav;
