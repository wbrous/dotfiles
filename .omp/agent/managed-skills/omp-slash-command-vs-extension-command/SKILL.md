---
name: omp-slash-command-vs-extension-command
description: "Use when implementing an omp custom slash command (e.g. \"/foo\") and deciding between a markdown file command (~/.omp/agent/commands/*.md) and a TS extension's pi.registerCommand — and when the command needs to run real subprocesses/scripts before involving the LLM."
---

## Two ways to add a slash command in omp

1. **Native markdown command**: `<cwd>/.omp/commands/<name>.md` (project) or `~/.omp/agent/commands/<name>.md` (user). Frontmatter + body text is expanded as a prompt template ($1, $ARGUMENTS, etc.) and sent to the LLM, which then uses its own tools (bash, edit...) to act. Zero code, but the agent decides *how* to run things — less deterministic, no guaranteed subprocess execution or JSON parsing.

2. **TS extension command**: file under `~/.omp/agent/extensions/*.ts` (or `<cwd>/.omp/extensions/`), exporting a default factory `(pi: ExtensionAPI) => { pi.registerCommand("name", { description, handler: async (args, ctx) => {...} }) }`. The handler is real TypeScript/JS code — run `child_process.execFileSync` for actual scripts, parse JSON output deterministically, then call `pi.sendMessage({...}, { triggerTurn: true })` to hand a *summary* to the agent for verification/next steps. This is the right choice whenever a command must: run external CLIs reliably, parse structured output, do deterministic pre/post-processing, then optionally still involve the LLM as a verification step.

## Practical pattern for "run scripts, then ask AI to verify"

```ts
import { execFileSync } from "node:child_process";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

export default function myExt(pi: ExtensionAPI) {
  pi.registerCommand("my-cmd", {
    description: "...",
    handler: async (args, ctx) => {
      const out = execFileSync("python3", ["script.py", "--json"], { encoding: "utf8" });
      const report = JSON.parse(out);
      // ... do deterministic work, maybe more subprocess calls ...
      pi.sendMessage(
        { customType: "my-report", content: `Results:\n${JSON.stringify(report)}\n\nVerify X, Y, Z.`, display: true, attribution: "user" },
        { triggerTurn: true } // hands off to the agent as a real turn so it actually acts/verifies
      );
    },
  });
}
```

- `ctx.ui.notify(msg, "info"|"error")` for lightweight side-channel status (no LLM turn).
- `pi.sendMessage(..., { triggerTurn: true })` is what actually gets the agent to *do* something with the results — without it, the command runs silently with no LLM involvement.
- Extension commands cannot call runtime actions (`pi.sendMessage`, etc.) synchronously at module load time — only from within `handler`/event callbacks, or you get `ExtensionRuntimeNotInitializedError`.
- Install by symlinking the source `.ts` file into `~/.omp/agent/extensions/<name>.ts` (or the project `.omp/extensions/`); restart omp or `/reload-plugins` to pick it up. Bundling sanity-check before install: `bun build path/to/ext.ts --target=node --outfile=/tmp/check.js` catches syntax errors even though the `@oh-my-pi/pi-coding-agent` types aren't resolvable standalone.

## Sharing config between a global git hook and an omp extension

If both a global git hook (installed via `core.hooksPath`) and an omp extension need to find the same external tool checkout, write a small conf file at install time (e.g. `~/.config/<tool>/global-hooks.conf` with `TOOL_HOME="/abs/path"`), sourced by the shell hook and read+regex-parsed by the TS extension. Keeps a single source of truth instead of duplicating path-discovery logic in two languages.
