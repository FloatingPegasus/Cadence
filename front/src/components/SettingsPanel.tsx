import type { ContinuityContext, Habit } from "../api";
import AIPrivacySettings from "./AIPrivacySettings";
import ContextManager from "./ContextManager";
import DataExportButton from "./DataExportButton";
import DevAIModels from "./DevAIModels";
import GoalsSettings from "./GoalsSettings";
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
      <h1 className="mb-6 text-base font-medium text-neutral-100">Settings</h1>
      <GoalsSettings />
      <HabitManager habits={habits} onChanged={onHabitsChanged} />
      <ContextManager contexts={contexts} onChanged={onContextsChanged} />
      <AIPrivacySettings />
      <section aria-labelledby="data-export-title" className="mt-6 border-t border-neutral-800 pt-6">
        <h2 id="data-export-title" className="text-sm font-medium text-neutral-200">
          Your data
        </h2>
        <p className="mt-1 mb-3 text-xs leading-5 text-neutral-500">
          Download a JSON copy of your account and history.
        </p>
        <DataExportButton />
      </section>
      {isDeveloper && <DevAIModels />}
    </div>
  );
}
