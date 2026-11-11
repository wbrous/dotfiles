// dotfiles-scan: /dotfiles-scan omp extension.
//
// On demand, this command tells the agent exactly how to survey $HOME for
// config worth adding to the dotfiles bare repo, under the standards in
// ~/Docs/git/dotfiles.md: only config written on purpose is a dotfile; theme
// output, app-saved state, installer output, other coding agents' files, and
// project source are not. Docs/ is the one tree added wholesale, through
// `dotfiles autoadd`.
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
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/** The bare-repo git prefix, as the `dotfiles` function expands it. */
const GIT = "git --git-dir='$HOME/.dotfiles' --work-tree='$HOME'";

/** Predefined scan scopes offered as autocomplete, plus free-form arg support. */
const SCAN_SCOPES: Record<string, string> = {
  docs: "only ~/Docs: run `dotfiles autoadd`, review, commit (no scouts)",
  config: "sweep only ~/.config",
  local: "sweep only ~/.local/bin and ~/.local/share",
  home: "sweep top-level dotfiles and the ~/.omp tree under $HOME",
};

/** Standards every verdict is judged against. Mirrors ~/Docs/git/dotfiles.md. */
const STANDARDS = [
  "A dotfile is config written ON PURPOSE by the user or their agent. Output is not config.",
  "NOT dotfiles, never add (verdict NO-GENERATED): files a theme or font hook rewrites " +
    "(omazed, omarchy-theme-sync, omarchy font-set, btop/zed/omp theme outputs); app-saved state " +
    "(window geometry, recent files, last-version markers, plugin-manager state, an app rewriting " +
    "its own settings on exit); installer output (native-messaging hosts, `.sample` files, " +
    "'managed by'/'do not edit' blocks); backups (`*.bak*`, `*.old`).",
  "NOT dotfiles (verdict NO-AGENT): config, skills, hooks, or themes of any coding agent other than omp. " +
    "omp is the only agent in use. Shared skills in ~/.agents/skills are the exception: omp reads them.",
  "NOT dotfiles (verdict NO-PROJECT): project source or archives (anything under ~/Projects); it belongs in its own repo.",
  "NOT dotfiles (verdict NO-SECRET): tokens, auth, sessions, history, databases, sockets, caches.",
  "NOT at a live path (verdict NO-LIVE): runtime-critical files the push itself depends on (gpg config, " +
    "pinentry, signing hooks). Track a copy under ~/.local/share/<topic>/ plus an install script.",
  "A good test: if a theme change, font change, or just launching the app would modify the file, it is output.",
].map((rule) => `  - ${rule}`);

/** The prompt injected into the agent to run the survey. `focus` may be empty. */
function buildSurveyPrompt(focus: string): string {
  const scope = focus.trim()
    ? `Narrow the sweep to ${focus} only (skip everything else).`
    : "Sweep the whole home directory for untracked config candidates.";

  return [
    "Run the dotfiles survey now, under ~/Docs/git/dotfiles.md. Do the following, in order, and do NOT skip a step:",
    "",
    `SCOPE: ${scope}`,
    "",
    "STANDARDS — judge every candidate against these:",
    ...STANDARDS,
    "",
    "STEP 1 — Docs (always, unless SCOPE excludes it): run `dotfiles autoadd`, then " +
      "`dotfiles diff --cached --stat -- Docs`. If anything is staged, commit it with ONE descriptive message " +
      "naming the areas touched (e.g. `docs(git): document dotfiles autoadd`). Never use a message like `update`. " +
      "If SCOPE is `docs`, stop after this step.",
    "",
    "STEP 2 — enumerate untracked candidates yourself, cheaply, before spawning scouts:",
    "  Run   " + GIT + " ls-tree -r --name-only HEAD   to snapshot the tracked list.",
    "  Diff that against the on-disk tree under the SCOPE. Drop every path matched by the exclude list " +
      "(`" + GIT + " check-ignore -v <path>`; the list is ~/.config/dotfiles/exclude) — those are already " +
      "decided. Drop symlinks into /usr/share/omarchy or ~/.agents. Ignore ~/Docs (STEP 1 owns it).",
    "  If nothing is left, say so plainly and stop.",
    "",
    "STEP 3 — fan out READ-ONLY scout subagents in PARALLEL via a single `task` batch, one task per " +
      "top-level cluster (e.g. `.config/<tool>` groups, `.local/bin`, `.local/share`, `~/.omp`), each with an " +
      "already-narrowed list of 5-20 paths. Give every scout the STANDARDS above verbatim. Each scout emits " +
      "EXACTLY one line per path: `<path> | <verdict> | <reason>` with verdict one of:",
    "    ADD            hand-authored config, passes every standard.",
    "    MAYBE          judgment call, needs a scrub, or empty/stub.",
    "    NO-GENERATED | NO-AGENT | NO-PROJECT | NO-SECRET | NO-LIVE   per STANDARDS.",
    "  Tell every scout to grep each candidate for secrets: " +
      "`token|secret|password|api[_-]?key|auth[_-]?|credential|bearer|ghp_|glpat-|ctx7sk|figd_|AKIA`, " +
      "and to say how the file got there (hand-written vs written by a tool).",
    "",
    "STEP 4 — commit the ADDs. Re-check each path against the STEP 2 tracked snapshot first (skip already-tracked). " +
      "The repo has ONE shared index: stage and commit strictly sequentially, one logical group at a time, " +
      "NEVER `add -A`, `add .`, or `commit -a`/`-am` (that is how theme output got swept into `update` commits). " +
      "Stage with   " + GIT + " add -- '<path>'   and commit with a message that says what the config does " +
      "(`Add hypr monitor layout`), never `update`. The gitleaks pre-commit hook runs on each commit; if it " +
      "blocks an ADD you believe is a false positive, report it under MAYBE instead of forcing GIT_ALLOW_SECRETS=1.",
    "  For each NO-GENERATED / NO-AGENT / NO-PROJECT path worth keeping out for good, append a rooted pattern to " +
      "~/.config/dotfiles/exclude (under the matching section) and commit that file.",
    "",
    "STEP 5 — report back, exactly in this format:",
    "  COMMITTED: <one line per commit: hash, message>",
    "  MAYBE: <one line per path left uncommitted, with the reason>",
    "  EXCLUDED: <one line per pattern added to the exclude list, with the verdict>",
    "",
    "Do not invent candidates or commit anything not verdict-ed ADD by a scout and verified untracked. " +
      "Do not rewrite history or push anything.",
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
