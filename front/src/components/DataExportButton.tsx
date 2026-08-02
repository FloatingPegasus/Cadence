import { useState } from "react";

import { fetchDataExport } from "../api";

function exportFilename() {
  return `cadence-export-${new Date().toISOString().slice(0, 10)}.json`;
}

function DataExportButton() {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setIsExporting(true);
    setError(null);
    try {
      const payload = await fetchDataExport();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exportFilename();
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not export data",
      );
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="text-right">
      <button
        type="button"
        onClick={handleExport}
        disabled={isExporting}
        className="px-3 py-1.5 text-sm rounded-lg border border-neutral-800 bg-neutral-900 text-neutral-400 transition-colors duration-150 hover:bg-neutral-800 hover:text-neutral-200 disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-400"
      >
        {isExporting ? "Exporting…" : "Export data"}
      </button>
      {error && (
        <p role="alert" className="mt-1 max-w-48 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}

export default DataExportButton;
