---
name: omp-mention-model-in-chat
description: "User asks how to mention/tag/select a specific model in omp chat composer (^provider/model, m1 agents, /model, --model)."
---

# Mentioning a specific model in omp chat

Docs live at `omp://` (read via `grep`/`read`; `find` may fail if judge keys are expired, so use `grep`). No dedicated user-facing page exists for `^` mentions; sources are `omp://tools/task.md` (line ~69), `omp://task-agent-discovery.md` (~267), `omp://slash-command-internals.md` (~220, ~364).

## Answer
- In the composer type `^provider/model` (e.g. `^openai/gpt-5.2`) or `^provider/model:level` (levels: off|minimal|low|medium|high|xhigh|max|auto|inherit).
- Each tag becomes a session-local agent pseudonym `m1`, `m2`, ... using the bundled `task` template pinned to that model. The main model spawns it with `agent: "m1"` in `task`, eval `agent()`, or `workpool()`.
- Mentions are expanded on normal user prompts before magic-keyword matching; also apply to agents-hub injected messages.
- A level tag fixes effort: the `effort` hint and per-call `model` are rejected for it. A tag without a level grants that model for per-call selection, subject to `task.perCallModelAllow`.
- Other routes: `/model` switches the main model; `omp --model <id-or-role>`; `@smol`/`@slow` role aliases are for settings/`--model`/frontmatter, not mentions.
- Unverified: composer autocomplete behavior for `^`.
