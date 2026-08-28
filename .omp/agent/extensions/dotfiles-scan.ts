// dotfiles-scan: /dotfiles-scan omp extension.
//
// On demand, this command tells the agent exactly how to run the "fan-out
// scout survey" from the dotfiles-bare-repo-gitleaks-hook skill: diff the
// tracked list against on-disk candidates, fan scout subagents out in parallel
// over path clusters, collect one-line `DEF ADD` / `MAYBE` / `SHOULDN'T ADD`
// verdicts, auto-commit the DEF ADDs (filtered against already-tracked paths),
// and report a MAYBE list and a NO list back to the user.
//
// The extension does NOT do the survey itself — the agent spawns the scout
// subagents through its own `task` tool (extensions have no way to spawn agent
// subagents). So the command's job is to inject a precise, self-contained
// prompt carrying the exact procedure, then let the agent execute it. The
// prompt is emitted via sendMessage(triggerTurn) so it becomes the next turn's
// instructions.
//
// Usage:
//   /dotfiles-scan                full sweep of $HOME for untracked candidates
//   /dotfiles-scan <scope>        narrow the sweep to a predefined scope
import { homedir } from "node:os";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/** The bare-repo git prefix, as the `dotfiles` alias expands it. */
const GIT = "git --git-dir='$HOME/.dotfiles' --work-tree='$HOME'";

/** Predefined scan scopes offered as autocomplete, plus free-form arg support. */
const SCAN_SCOPES: Record<string, string> = {
  skills: "sweep only skill dirs under ~/.agents and AI-tool configs",
  config: "sweep only ~/.config",
  home: "sweep top-level dotfiles under $HOME",
};

/** The prompt injected into the agent to run the scout survey. `focus` may be empty. */
function buildSurveyPrompt(focus: string): string {
  const scope = focus.trim()
    ? `Narrow the sweep to ${focus} only (skip everything else).`
    : "Sweep the whole home directory for untracked config / skills / dotfiles candidates.";

  return [
    "Run the dotfiles fan-out scout survey now (per the dotfiles-bare-repo-gitleaks-hook skill). " +
      "Do the following, in order, and do NOT skip a step:",
    "",
    `SCOPE: ${scope}`,
    "",
    "STEP 1 — enumerate untracked candidates yourself, cheaply, before spawning scouts:",
    "  Run   " + GIT +
      " ls-tree -r --name-only HEAD --sort=name   and snapshot the tracked list.",
    "  Diff that against the on-disk tree under $HOME (and ~/.config, ~/.claude, ~/.codex, ~/.gemini, " +
      "~/.cursor, ~/.pi, ~/.omp, ~/.grok, ~/.commandcode, ~/.factory, ~/.kimi-code, ~/.copilot, etc.) " +
      "to produce the explicit untracked-candidate list per cluster. Give each scout its already-narrowed " +
      "path list (5-20 paths is fine here since scouts are read-only).",
    "",
    "STEP 2 — fan out scout subagents in PARALLEL via a single `task` batch (one task per cluster):",
    "  Group candidates by tool/vendor — one cluster per AI coding tool and one '.config/<misc>' cluster. " +
      "Each scout is READ-ONLY. Instruct each scout to emit EXACTLY one line per path with a verdict tag:",
    "    DEF ADD        clean, useful config — safe to commit as-is.",
    "    MAYBE          needs a scrub, is a judgment call, is an auto-generated stub, an empty dir, or " +
      "a symlink into a harness/system skill store (skip by default, list it).",
    "    SHOULDN'T ADD  carries secrets / account / session data — this is the NO list.",
    "  Tell every scout to grep for secret patterns in EVERY candidate: " +
      "`token|secret|password|api[_-]?key|auth[_-]?|credential|bearer|ghp_|glpat-|ctx7sk|figd_|AKIA` " +
      "and to recurse one level deeper into likely secret-bearing files (e.g. *.json mcpServers blocks, " +
      "app plugin_config/config.json, .docker/.token_seed, browser session dirs).",
    "",
    "STEP 3 — auto-commit the DEF ADDs, filtered against already-tracked:",
    "  Before staging ANY path, re-check it against the tracked snapshot from STEP 1 — skip any path " +
      "already tracked (avoids a wasted commit line and a muddied 'what's new' signal).",
    "  Then, one path (or one logical dir) at a time — NEVER `add -A`/`add .` — stage with:",
    "    " + GIT + " add -- '<path>'",
    "  and commit each with a clear message (e.g. `Add <path>`). Keep commits small and on-topic.",
    "  The global gitleaks pre-commit hook runs on each commit. If it blocks on a DEF ADD you believe " +
      "is a false positive, report it in MAYBE instead of forcing with GIT_ALLOW_SECRETS=1.",
    "",
    "STEP 4 — report back, exactly in this format:",
    "  DEF ADD COMMITTED: <one line per path committed, with its commit>",
    "  MAYBE: <one line per path left uncommitted — reason for each: stub/empty/judgment-call/secret-suspect>",
    "  NO: <one line per path explicitly not added — the SHOULDN'T ADD verdicts, with the reason: " +
      "secret/account/session data>",
    "  If SCOPE produced zero untracked candidates, say so plainly and stop.",
    "",
    "Do not invent candidates or commit anything not verdict-ed DEF ADD by a scout and verified untracked. " +
      "Do not touch repo history or push anything.",
  ].join("\n");
}

export default function dotfilesScanExtension(pi: ExtensionAPI): void {
  pi.registerCommand("dotfiles-scan", {
    description:
      "Survey $HOME for untracked config/skills to add to the dotfiles repo: spawns parallel scout subagents, " +
      "auto-commits the DEF ADDs, and reports MAYBE and NO lists.",
    getArgumentCompletions: (prefix) => {
      const p = prefix.trim().toLowerCase();
      return Object.entries(SCAN_SCOPES)
        .filter(([value]) => value.startsWith(p))
        .map(([value, description]) => ({ value, label: value, description }));
    },
    handler: async (args) => {
      pi.sendMessage(
        {
          customType: "dotfiles-scan-instructions",
          content: buildSurveyPrompt(args ?? ""),
          display: true,
          attribution: "user",
        },
        { triggerTurn: true },
      );
    },
  });
}
