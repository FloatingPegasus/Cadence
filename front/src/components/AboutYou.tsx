import { useEffect, useState } from "react";

import { fetchContextPreview, type Habit } from "../api";
import { useAuth } from "../contexts/AuthContext";
import { todayAsLocalDate } from "../time";
import GoalsSettings from "./GoalsSettings";
import HabitManager from "./HabitManager";

interface AboutYouProps {
  habits: Habit[];
  onHabitsChanged: () => void;
}

export default function AboutYou({ habits, onHabitsChanged }: AboutYouProps) {
  const { user, aiEnabled, updateAbout } = useAuth();
  const [about, setAbout] = useState(user?.about ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setAbout(user?.about ?? "");
  }, [user?.about]);

  async function saveAbout() {
    if (about.trim() === (user?.about ?? "")) return;
    setError(null);
    try {
      await updateAbout(about);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save");
    }
  }

  return (
    <section aria-labelledby="about-title">
      <h2 id="about-title" className="cadence-kicker">
        About you
      </h2>
      {aiEnabled ? (
        <textarea
          aria-labelledby="about-title"
          value={about}
          onChange={(event) => setAbout(event.target.value)}
          onBlur={() => void saveAbout()}
          maxLength={1500}
          placeholder="Who you are, what you're working toward, and what helps when things get hard"
          className="cadence-field mt-4 min-h-28 resize-none"
        />
      ) : null}
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {error}
        </p>
      )}
      <GoalsSettings />
      <HabitManager habits={habits} onChanged={onHabitsChanged} />
      {aiEnabled ? <ContextPreview /> : null}
    </section>
  );
}

function ContextPreview() {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(open: boolean) {
    if (!open) return;
    setError(null);
    try {
      setText((await fetchContextPreview(todayAsLocalDate())).text);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load");
    }
  }

  return (
    <details
      className="cadence-fold"
      onToggle={(event) => void load(event.currentTarget.open)}
    >
      <summary className="text-sm text-neutral-400 hover:text-neutral-200">
        What Cadence sees
      </summary>
      {error ? (
        <p role="alert" className="mt-3 text-xs text-red-400">
          {error}
        </p>
      ) : (
        <pre className="mt-3 mb-2 max-h-80 overflow-auto whitespace-pre-wrap break-words font-sans text-xs leading-5 text-neutral-400">
          {text === null ? "Loading…" : text || "Nothing yet."}
        </pre>
      )}
    </details>
  );
}
