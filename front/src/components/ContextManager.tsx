import { useState, type FormEvent } from "react";

import {
  archiveContext,
  createContext,
  updateContext,
  type ContinuityContext,
  type ContinuityContextKind,
} from "../api";

interface ContextManagerProps {
  contexts: ContinuityContext[];
  onChanged: () => void;
}

const kindLabels: Record<ContinuityContextKind, string> = {
  project: "Project",
  learning: "Learning",
  area: "Area",
};

export default function ContextManager({
  contexts,
  onChanged,
}: ContextManagerProps) {
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] =
    useState<ContinuityContextKind>("project");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");
  const [editingKind, setEditingKind] =
    useState<ContinuityContextKind>("project");
  const [error, setError] = useState<string | null>(null);

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      await createContext(name, newKind);
      setNewName("");
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not add area",
      );
    }
  }

  async function save(event: FormEvent<HTMLFormElement>, contextId: number) {
    event.preventDefault();
    const name = editingName.trim();
    if (!name) return;
    setError(null);
    try {
      await updateContext(contextId, name, editingKind);
      setEditingId(null);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not update area",
      );
    }
  }

  async function archive(contextId: number) {
    setError(null);
    try {
      await archiveContext(contextId);
      onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not archive area",
      );
    }
  }

  return (
    <details>
      <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-200">
        Manage areas
      </summary>
      <div className="pt-5">
        <form
          onSubmit={add}
          className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_auto]"
        >
          <label className="sr-only" htmlFor="new-context-name">
            New area name
          </label>
          <input
            id="new-context-name"
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="Add a project or area"
            maxLength={100}
            className="min-w-0 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-neutral-600"
          />
          <select
            value={newKind}
            onChange={(event) =>
              setNewKind(event.target.value as ContinuityContextKind)
            }
            aria-label="Area type"
            className="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-400 outline-none focus:border-neutral-600"
          >
            {Object.entries(kindLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button className="rounded-lg bg-neutral-800 px-3 py-2 text-xs text-neutral-200 hover:bg-neutral-700">
            Add
          </button>
        </form>

        <div className="mt-4 space-y-2">
          {contexts.map((context) =>
            editingId === context.id ? (
              <form
                key={context.id}
                onSubmit={(event) => save(event, context.id)}
                className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_auto_auto]"
              >
                <input
                  aria-label={`Edit ${context.name}`}
                  value={editingName}
                  onChange={(event) => setEditingName(event.target.value)}
                  maxLength={100}
                  className="min-w-0 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 outline-none"
                />
                <select
                  value={editingKind}
                  onChange={(event) =>
                    setEditingKind(
                      event.target.value as ContinuityContextKind,
                    )
                  }
                  aria-label="Area type"
                  className="rounded-lg border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-xs text-neutral-400 outline-none"
                >
                  {Object.entries(kindLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <button className="text-xs text-neutral-300">Save</button>
                <button
                  type="button"
                  onClick={() => setEditingId(null)}
                  className="text-xs text-neutral-600"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <div
                key={context.id}
                className="flex items-center justify-between gap-3 px-2 py-1.5"
              >
                <span className="min-w-0 text-sm text-neutral-300">
                  {context.name}
                  <span className="ml-2 text-xs text-neutral-600">
                    {kindLabels[context.kind]}
                  </span>
                </span>
                <div className="flex shrink-0 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(context.id);
                      setEditingName(context.name);
                      setEditingKind(context.kind);
                    }}
                    className="text-xs text-neutral-500 hover:text-neutral-300"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => archive(context.id)}
                    className="text-xs text-neutral-600 hover:text-red-400"
                  >
                    Archive
                  </button>
                </div>
              </div>
            ),
          )}
        </div>

        {error && (
          <p role="alert" className="mt-3 text-xs text-red-400">
            {error}
          </p>
        )}
      </div>
    </details>
  );
}
