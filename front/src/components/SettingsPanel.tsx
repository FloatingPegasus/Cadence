import type { ContinuityContext, Habit } from "../api";
import { useAuth } from "../contexts/AuthContext";
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
  const { user } = useAuth();
  const claimed = Boolean(user && !user.is_guest);

  return (
    <div>
      <h1 className="cadence-title mb-10 text-2xl font-medium text-neutral-100">
        Settings
      </h1>
      <div className="space-y-5">
        <div className="cadence-surface">
          <GoalsSettings />
        </div>
        {habits.length > 0 ? (
          <div className="cadence-surface">
            <HabitManager habits={habits} onChanged={onHabitsChanged} />
          </div>
        ) : null}
        <div className="cadence-surface">
          <ContextManager contexts={contexts} onChanged={onContextsChanged} />
        </div>
        {claimed ? (
          <div className="cadence-surface">
            <AIPrivacySettings />
          </div>
        ) : null}
        {claimed ? (
          <section aria-labelledby="data-export-title" className="cadence-surface">
            <h2 id="data-export-title" className="cadence-kicker">
              Your data
            </h2>
            <div className="mt-4">
              <DataExportButton />
            </div>
          </section>
        ) : null}
        {user ? (
          <section aria-labelledby="account-title" className="cadence-surface">
            <h2 id="account-title" className="cadence-kicker">
              Account
            </h2>
            <div className="mt-4">
              <LogoutButton />
            </div>
          </section>
        ) : null}
        {isDeveloper && (
          <div className="cadence-surface">
            <DevAIModels />
          </div>
        )}
      </div>
    </div>
  );
}
