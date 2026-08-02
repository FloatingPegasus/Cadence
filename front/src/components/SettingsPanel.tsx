import type { ContinuityContext, Habit } from "../api";
import AIPrivacySettings from "./AIPrivacySettings";
import ContextManager from "./ContextManager";
import DataExportButton from "./DataExportButton";
import DevAIModels from "./DevAIModels";
import HabitManager from "./HabitManager";

interface SettingsPanelProps {
  habits: Habit[];
  contexts: ContinuityContext[];
  isDeveloper: boolean;
  onHabitsChanged: () => void;
  onContextsChanged: () => void;
}

export default function SettingsPanel({
  habits,
  contexts,
  isDeveloper,
  onHabitsChanged,
  onContextsChanged,
}: SettingsPanelProps) {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-base font-medium text-neutral-100">Settings</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Manage structure, privacy, and local data.
        </p>
      </div>
      <HabitManager habits={habits} onChanged={onHabitsChanged} />
      <ContextManager contexts={contexts} onChanged={onContextsChanged} />
      <AIPrivacySettings />
      <section aria-labelledby="data-export-title" className="mt-6 border-t border-neutral-800 pt-6">
        <h2 id="data-export-title" className="text-sm font-medium text-neutral-200">
          Your data
        </h2>
        <p className="mt-1 mb-3 text-xs leading-5 text-neutral-500">
          Download a versioned JSON copy of your account and continuity record.
        </p>
        <DataExportButton />
      </section>
      {isDeveloper && <DevAIModels />}
    </div>
  );
}
