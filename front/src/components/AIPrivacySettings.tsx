import { useEffect, useState } from "react";

import { useAuth } from "../contexts/AuthContext";

export default function AIPrivacySettings() {
  const { user, updateAIPrivacy } = useAuth();
  const [consent, setConsent] = useState(
    user?.ai_processing_consent ?? false,
  );
  const [redaction, setRedaction] = useState(
    user?.ai_redaction_enabled ?? true,
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setConsent(user?.ai_processing_consent ?? false);
    setRedaction(user?.ai_redaction_enabled ?? true);
  }, [user?.ai_processing_consent, user?.ai_redaction_enabled]);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      await updateAIPrivacy(consent, redaction);
      setMessage("AI privacy preferences saved.");
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Could not save AI preferences",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="ai-privacy-title" className="border-t border-neutral-800 pt-6">
      <h2 id="ai-privacy-title" className="text-sm font-medium text-neutral-200">
        Automatic summaries
      </h2>
      <p className="mt-1 max-w-2xl text-xs leading-5 text-neutral-500">
        Optional summaries use the configured AI service. Only the source
        material needed for a summary is sent. Manual summaries and all local
        features work without consent.
      </p>
      <div className="mt-4 space-y-4">
        <label className="flex items-start gap-3 text-sm text-neutral-300">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            className="mt-0.5 accent-violet-400"
          />
          <span>
            Allow automatic summaries to use today’s notes
            <span className="mt-1 block text-xs leading-5 text-neutral-600">
              When enabled, Cadence updates the summary after you save new
              notes or log a moment.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-3 text-sm text-neutral-300">
          <input
            type="checkbox"
            checked={redaction}
            onChange={(event) => setRedaction(event.target.checked)}
            className="mt-0.5 accent-violet-400"
          />
          <span>
            Redact common email addresses and phone-like numbers
            <span className="mt-1 block text-xs leading-5 text-neutral-600">
              Your original local records are never changed.
            </span>
          </span>
        </label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 transition-colors duration-150 hover:bg-neutral-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save AI preferences"}
        </button>
        {message && <p role="status" className="text-xs text-neutral-500">{message}</p>}
      </div>
    </section>
  );
}
