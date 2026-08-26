# Project Instructions

- **Keyboard shortcuts:** When adding or changing shortcuts, start with
  `keybindings.ts` and update the Keyboard Shortcuts dialog to match.
- **UI copy:** Do not add subtitles, helper text, or descriptive copy beneath
  headings, labels, cards, or settings by default. Prefer one concise,
  self-explanatory heading or label. Add supporting copy only when requested or
  necessary to prevent misunderstanding or error, and never restate the heading.
- **Code comments:** Do not add comments that narrate minor events or fixes.
  Include historical context only when it explains an important decision, such
  as a major system migration.

## Working Style

- **Clarify consequential ambiguity:** State material assumptions. Ask before
  acting when different interpretations would materially change the result,
  and mention a simpler option when one exists.
- **Prefer the smallest solution:** Implement only what the task requires.
  Avoid speculative features, single-use abstractions, and unnecessary
  configuration.
- **Keep changes surgical:** Touch only relevant code and match the existing
  style. Remove code made obsolete by your change, but report unrelated cleanup
  instead of including it.
- **Verify the outcome:** Define success criteria for non-trivial work. Reproduce
  bugs with tests when practical, verify behavior after changes, and keep
  iterating until the checks pass.
- **Protect live state during verification:** Never overwrite, replace, or delete
  live project config or data, especially `.env`; use isolated `mktemp` paths,
  disposable test databases, or explicit temporary `--env-file` values, and
  preserve/restore any pre-existing path.
- Use judgment for trivial changes; they do not need unnecessary process.
