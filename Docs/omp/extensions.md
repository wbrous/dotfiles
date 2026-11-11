# omp extensions: commands, notifications, and autosync lessons

Scope: writing omp TypeScript extensions — slash commands vs markdown commands, background notifications, terminal image widgets, and the reusable lesson from the retired managed-skill autosync extension.

## Slash command: markdown file vs `pi.registerCommand`

**Symptom:** need a custom `/foo` command that runs real subprocesses/scripts before involving the LLM, and deciding which mechanism to use.

**Fix:** two mechanisms:

1. **Native markdown command**: `<cwd>/.omp/commands/<name>.md` (project) or `~/.omp/agent/commands/<name>.md` (user). Frontmatter + body expanded as a prompt template (`$1`, `$ARGUMENTS`); the LLM then uses its own tools. Zero code, but nondeterministic — no guaranteed subprocess execution or JSON parsing.
2. **TS extension command**: file under `~/.omp/agent/extensions/*.ts` (or `<cwd>/.omp/extensions/`), exporting a default factory `(pi: ExtensionAPI) => { pi.registerCommand("name", { description, handler: async (args, ctx) => {...} }) }`. Real code — `child_process.execFileSync` for scripts, parse JSON deterministically, then `pi.sendMessage({...}, { triggerTurn: true })` to hand a summary to the agent for verification. Use this whenever a command must run external CLIs reliably, parse structured output, or do deterministic pre/post-processing.

```ts
import { execFileSync } from "node:child_process";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export default function myExt(pi: ExtensionAPI) {
  pi.registerCommand("my-cmd", {
    description: "...",
    handler: async (args, ctx) => {
      const out = execFileSync("python3", ["script.py", "--json"], { encoding: "utf8" });
      const report = JSON.parse(out);
      pi.sendMessage(
        { customType: "my-report", content: `Results:\n${JSON.stringify(report)}\n\nVerify X, Y, Z.`, display: true, attribution: "user" },
        { triggerTurn: true }
      );
    },
  });
}
```

**Gotchas:** `ctx.ui.notify(msg, "info"|"error")` is a lightweight side channel (no LLM turn); `pi.sendMessage(..., { triggerTurn: true })` is what makes the agent actually act. Extension commands cannot call runtime actions synchronously at module load — only inside `handler`/event callbacks, or `ExtensionRuntimeNotInitializedError`. Install by symlinking the `.ts` into `~/.omp/agent/extensions/<name>.ts`; restart omp or `/reload-plugins`. Bundling sanity check: `bun build path/to/ext.ts --target=node --outfile=/tmp/check.js` (the `@oh-my-pi/pi-coding-agent` types won't resolve standalone). If both a global git hook and an extension need the same tool checkout path, write a conf file at install time (e.g. `~/.config/<tool>/global-hooks.conf` with `TOOL_HOME="/abs/path"`), sourced by the shell hook and regex-parsed by the TS extension.

_Migrated from: omp-slash-command-vs-extension-command_

## Background notifications: `deliverAs: "nextTurn"`, not `triggerTurn`

**Symptom:** an extension notifies the agent (auto-commit confirmations, task-completion messages) via `pi.sendMessage(message, { triggerTurn: true })`, which schedules an internal continuation turn — burning tokens on a synthetic turn and racing ahead of autolearn.

**Cause:** verified in `src/session/agent-session.ts`, `sendCustomMessage`.

**Fix:**

```ts
pi.sendMessage({ customType: "...", content: "...", display: true, attribution: "user" },
  { deliverAs: "nextTurn" });
```

While streaming (the usual case — fired from a `tool_result` handler mid-turn), the message is queued via `#queueHiddenNextTurnMessage(msg, false)`: hidden, no continuation scheduled, consumed on the user's next real message. When idle: appended to the session, no new turn started. `deliverAs: "nextTurn"` keeps the message out of the editable pending-message UI. Takes effect on next session reload.

**When to keep `triggerTurn: true`:** commands the user deliberately invokes that must make the agent act **now** — e.g. a `/dotfiles-scan`-style slash command whose `sendMessage` is an instruction prompt. Rule: notification (informational, no action required) → `deliverAs: "nextTurn"`; instruction (must trigger action) → `triggerTurn: true`.

_Migrated from: omp-extension-notification-nextturn-delivery_

## Ambient terminal image widget (pet/sprite) via `setWidget`

**Symptom:** building an extension that renders animated terminal graphics (a "pet" widget, live status sprite) via `ctx.ui.setWidget` + Kitty/Sixel/iTerm2 image protocols, ported from OpenCode Codex CLI's `codex-rs/tui/src/pets/*` (PR #21206 — full row/frame/timing spec lives there, read it directly).

**Fix — overlap instead of reserving a block:** `setWidget` reserves exactly as many rows as `Component.render(width)` returns. A naive port of `pi-tui`'s `Image` reserves N rows (N−1 blank fillers + one real line), pushing a visible gap above the composer. Instead report exactly **one** line and paint the N-row image with cursor save/move/restore:

```ts
const SAVE_CURSOR = "\x1b7";
const RESTORE_CURSOR = "\x1b8";
const moveUp = cursorRows > 0 ? `\x1b[${cursorRows}A` : "";
return [cursorRows > 0 ? SAVE_CURSOR + moveUp + content + RESTORE_CURSOR : body];
```

This tells layout the widget is 1 row tall while the image paints upward over the transcript tail — genuine overlap, not a reserved block.

**Right-anchor every row individually:** if the renderer's "unicode placeholder" path returns multiple real text rows (`result.lines`), shift each row with non-destructive Cursor Forward (CUF, `ESC[nC`), never literal spaces (spaces erase whatever was in those cells):

```ts
const moveRight = padCols > 0 ? `\x1b[${padCols}C` : "";
const content = result.lines
  .map((line, i) => (i === 0 ? transmitPrefix : "") + moveRight + line)
  .join("\r\n");
return [SAVE_CURSOR + moveUp + content + RESTORE_CURSOR];
```

Single-command protocols (direct-placement Kitty, Sixel, iTerm2 — anything returning `result.sequence`) need only one shift: the terminal expands the image over N rows itself. **Limitation:** real text reflow (transcript narrowing its wrap width to leave a gutter, like Codex's Rust TUI `history_wrap_width`) is impossible through the extension API — no hook into the core renderer. State this explicitly.

**Gotcha — `ctx.ui.custom()` overlay is a modal primitive, not ambient decor:** tracing `TUI.showOverlay` in `packages/tui/src/tui.ts` shows it unconditionally `setFocus(component)` + `terminal.hideCursor()` (undone only when `overlayStack.length === 0`). Never-`done()` overlay + `tui.setFocus(priorFocus)` hack does NOT reliably restore typing — confirmed live: keystrokes stopped reaching the composer. Use `ctx.ui.setWidget(key, factory, { placement: "aboveEditor" | "belowEditor" })` for persistent decor; it doesn't touch focus or cursor.

**Gotcha — `Bun.$` shell result field is `exitCode`, not `code`:**

```ts
const { stdout, code } = await Bun.$`which magick`.quiet().nothrow();
if (code === 0) { ... } // BUG: `code` is always undefined, branch never fires
```

`code` silently exists as `undefined` (no TS error on loose destructure), so `code !== 0` is always true — every success check takes the failure branch. `ctx.ui.notify(...)` swallows this in headless/print mode (no-op there), so it passes smoke tests with zero visible errors while doing nothing. Verify shell-gated logic by its on-disk side effects (e.g. expected cache files), not by "no error printed".

**Verifying without a screenshot:** `hub start` an interactive omp TUI, use `hub logs` to read raw captured output. On a Kitty-capable terminal (`xterm-kitty`), look for the `U+10EEEE` placeholder repeated with row/column combining diacritics — its presence over time (matching animation frame timing) confirms the live-graphics path fires, not text fallback. To verify focus: `hub send` literal text into the composer and grep subsequent `hub logs` for it landing in the input area.

_Migrated from: omp-extension-codex-pet-terminal-image_

## Reusable lesson from the retired managed-skill autosync extension

The `managed-skill-dotfiles` extension itself is being deleted with the skill system — do not reimplement it. Two facts worth keeping for any future extension that runs git against the dotfiles bare repo:

- **`pi.exec` does NOT forward `env`** (`ExecOptions` has only `cwd`/`signal`/`timeout`; an `env` option is silently dropped). Target the bare repo with leading global flags, not `GIT_DIR`/`GIT_WORK_TREE` env vars:
  ```ts
  pi.exec("git", [`--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args], { cwd: homedir() });
  ```
- **`OMPCODE=1` must be a shell prefix, not `process.env`.** The shared `prepare-commit-msg` hook appends `Co-authored-by: wbrous-dev-ai` only when `OMPCODE=1` is in the git subprocess env, but the harness injects `OMPCODE=1` only into the per-tool bash env, not the omp process env extensions run in. `process.env.OMPCODE = "1"` before `pi.exec` empirically did NOT propagate (commit `52ad597` lacked the co-author). Working approach — run git through a shell:
  ```ts
  const argv = ["git", `--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args];
  const cmd = `OMPCODE=1 ${argv.map(shq).join(" ")}`;
  const result = await pi.exec("/bin/sh", ["-c", cmd], { cwd: homedir() });
  ```
  with `shq(s) = "'" + s.replace(/'/g, `'\\''`) + "'"` so names/paths can't escape. Verified: commits `eae8f1c` (create) and `7394186` (delete) both carried the trailer.
- Related hook idea worth reusing: hook the `tool_result` event (`{ toolName, input, isError }`), filter on the tool of interest, skip `isError`, and dedupe rapid same-target mutations with a per-name `inFlight` set. Guardrails that worked: only touch the single target path (never `add -A`); skip no-ops via `git diff --cached --quiet -- <path>`; never bypass gitleaks (`GIT_ALLOW_SECRETS=1` stays a human escape hatch), surfacing hook stderr via `sendMessage({ triggerTurn: true })`.

_Migrated from: managed-skill-dotfiles-autosync-extension_
