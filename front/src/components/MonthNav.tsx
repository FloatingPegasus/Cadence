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
    <div className="flex items-center justify-center gap-3 mb-8">
      <button
        type="button"
        aria-label="Previous month"
        onClick={() => go(-1)}
        className="px-3 py-1.5 text-sm rounded-lg border border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
      >
        &larr;
      </button>
      <span className="text-sm font-medium text-neutral-100 w-32 text-center">
        {label}
      </span>
      <button
        type="button"
        aria-label="Next month"
        onClick={() => go(1)}
        className="px-3 py-1.5 text-sm rounded-lg border border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 transition-colors"
      >
        &rarr;
      </button>
    </div>
  );
}

export default MonthNav;
