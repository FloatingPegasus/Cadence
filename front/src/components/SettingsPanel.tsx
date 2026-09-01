import type { ContinuityContext, Habit } from "../api";
import AIPrivacySettings from "./AIPrivacySettings";
import ContextManager from "./ContextManager";
import DataExportButton from "./DataExportButton";
import DevAIModels from "./DevAIModels";
import GoalsSettings from "./GoalsSettings";
import HabitManager from "./HabitManager";
import LogoutButton from "./LogoutButton";

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
      <h1 className="cadence-title mb-10 text-2xl font-medium text-neutral-100">
        Settings
      </h1>
      <div className="space-y-5">
        <div className="cadence-surface">
          <GoalsSettings />
        </div>
        <div className="cadence-surface">
          <HabitManager habits={habits} onChanged={onHabitsChanged} />
        </div>
        <div className="cadence-surface">
          <ContextManager contexts={contexts} onChanged={onContextsChanged} />
        </div>
        <div className="cadence-surface">
          <AIPrivacySettings />
        </div>
        <section aria-labelledby="data-export-title" className="cadence-surface">
          <h2 id="data-export-title" className="cadence-kicker">
            Your data
          </h2>
          <div className="mt-4">
            <DataExportButton />
          </div>
        </section>
        <section aria-labelledby="account-title" className="cadence-surface">
          <h2 id="account-title" className="cadence-kicker">
            Account
          </h2>
          <div className="mt-4">
            <LogoutButton />
          </div>
        </section>
        {isDeveloper && (
          <div className="cadence-surface">
            <DevAIModels />
          </div>
        )}
      </div>
    </div>
  );
}
