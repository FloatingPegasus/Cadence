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
    <div>
      <button
        type="button"
        onClick={handleExport}
        disabled={isExporting}
        className="text-sm text-neutral-500 transition-colors duration-150 hover:text-neutral-200 disabled:cursor-wait disabled:opacity-60"
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
