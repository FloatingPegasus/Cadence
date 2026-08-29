import { useEffect, useState } from "react";
import {
  fetchAIModels,
  testAIModels,
  type AIModelRegistry,
} from "../api";

export default function DevAIModels() {
  const [registry, setRegistry] = useState<AIModelRegistry | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAIModels().then(setRegistry).catch(() => setRegistry(null));
  }, []);

  async function refresh() {
    setError(null);
    try {
      setRegistry(await fetchAIModels(true));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Refresh failed");
    }
  }

  async function test(modelId: string) {
    setTesting(modelId);
    setError(null);
    try {
      await testAIModels([modelId]);
      setRegistry(await fetchAIModels());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Model test failed");
    } finally {
      setTesting(null);
    }
  }

  async function testAll() {
    if (
      !window.confirm(
        `Test all ${registry?.models.length ?? 0} discovered chat models? This uses one NVIDIA request per model and may hit free-tier limits.`,
      )
    ) {
      return;
    }
    setTestingAll(true);
    setError(null);
    try {
      await testAIModels([], true);
      setRegistry(await fetchAIModels());
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Bulk model test failed",
      );
    } finally {
      setTestingAll(false);
    }
  }

  if (!registry) return null;

  return (
    <details>
      <summary className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-300">
        Developer · NVIDIA models
      </summary>
      <div className="pt-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs text-neutral-500">
              Ranking {registry.ranking_version} · {registry.models.length} chat
              models
            </p>
            {!registry.configured && (
              <p className="mt-1 text-xs text-amber-500">
                Add CADENCE_AI_API_KEY to .env to discover and test models.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={testAll}
              disabled={
                !registry.configured ||
                registry.models.length === 0 ||
                testing !== null ||
                testingAll
              }
              className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900 disabled:opacity-40"
            >
              {testingAll ? "Testing all…" : "Test all"}
            </button>
            <button
              onClick={refresh}
              disabled={!registry.configured || testingAll}
              className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900 disabled:opacity-40"
            >
              Refresh catalog
            </button>
          </div>
        </div>
        <div className="mt-4 max-h-96 space-y-2 overflow-y-auto">
          {registry.models.map((model, index) => (
            <div
              key={model.id}
              className="grid grid-cols-[2rem_1fr_auto_auto] items-center gap-3 rounded-lg bg-neutral-950/60 px-3 py-2"
            >
              <span className="text-xs text-neutral-700">#{index + 1}</span>
              <div className="min-w-0">
                <p className="truncate text-xs text-neutral-300">
                  {model.model_id}
                </p>
                <p className="mt-0.5 text-[11px] text-neutral-600">
                  strength {model.strength_score}
                  {model.latency_ms != null && ` · ${model.latency_ms} ms`}
                </p>
              </div>
              <span className="text-[11px] text-neutral-500">
                {model.health_status}
              </span>
              <button
                onClick={() => test(model.model_id)}
                disabled={testing !== null || testingAll}
                className="rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:bg-neutral-900 disabled:opacity-40"
              >
                {testing === model.model_id ? "Testing…" : "Test"}
              </button>
            </div>
          ))}
        </div>
        {(error || registry.sync_error) && (
          <p className="mt-3 text-xs text-red-400">
            {error || registry.sync_error}
          </p>
        )}
      </div>
    </details>
  );
}
