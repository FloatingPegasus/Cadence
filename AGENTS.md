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

Bias caution over speed except on trivial work. Skip the ceremony when the
change is obvious.

- **Think first.** State material assumptions. If interpretations would change
  the result, present them instead of picking one. Name what is unclear and
  ask. Mention a simpler option when one exists, and push back when the
  request would add unfinished complexity.
- **Smallest complete solution.** Implement only what the task requires. No
  extra features, single-use abstractions, unrequested configurability, or
  error handling for impossible cases. Prefer existing project libraries over
  new packages or a hand-rolled copy. Remove obsolete paths instead of adding
  shims, fallbacks, or compatibility layers. If the change could be much
  shorter, rewrite it.
- **Surgical diffs.** Every changed line should trace to the request. Match
  existing style. Do not reformat, refactor, or delete unrelated code; mention
  leftover dead code instead. Do remove imports, variables, and functions that
  your change made unused.
- **Verify.** For non-trivial work, name a check you can run. Reproduce bugs
  with tests when practical. Keep iterating until that check passes. Multi-step
  work needs a verify for each step, not “make it work.”
- **Protect live state.** Never overwrite, replace, or delete live project
  config or data, especially `.env`. Use isolated `mktemp` paths, disposable
  test databases, or explicit temporary `--env-file` values, and
  preserve/restore any pre-existing path.
