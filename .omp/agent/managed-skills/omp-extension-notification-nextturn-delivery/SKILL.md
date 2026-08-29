---
name: omp-extension-notification-nextturn-delivery
description: "Use when writing an omp extension that sends background notifications via pi.sendMessage (e.g. auto-commit reports, task-completion messages) — covers why deliverAs: \"nextTurn\" WITHOUT triggerTurn makes the message ride along with the next real user message instead of scheduling a token-costing continuation turn, and when to keep triggerTurn (commands that must make the agent act immediately)."
---

# omp extension notification delivery: nextTurn vs triggerTurn

## The problem

Extensions that notify the agent (auto-commit confirmations, error reports, etc.) via `pi.sendMessage(message, { triggerTurn: true })` schedule an **internal continuation turn** that consumes the message immediately — burning tokens on a synthetic turn, and racing ahead of omp's autolearn, which may be about to capture a new skill from the same session (also wasting tokens).

## The fix: `deliverAs: "nextTurn"`, no `triggerTurn`

```ts
pi.sendMessage({ customType: "...", content: "...", display: true, attribution: "user" },
  { deliverAs: "nextTurn" });
```

Semantics (verified in `src/session/agent-session.ts`, `sendCustomMessage`):
- **While streaming** (the usual case — the notification fires from a `tool_result` handler mid-turn): message is queued via `#queueHiddenNextTurnMessage(msg, false)` — hidden, **no continuation scheduled** — and consumed on the next turn, which will be the user's next real message.
- **When idle**: `agent.appendMessage(...)` + `appendCustomMessageEntry(...)` — appended to session, no new turn started; rides the next turn.
- `deliverAs: "nextTurn"` keeps the message out of the editable pending-message UI.

## When to KEEP `triggerTurn: true`

Commands the user deliberately invokes that must make the agent act **now** — e.g. a `/dotfiles-scan`-style slash command whose `sendMessage` is an instruction prompt the agent must execute immediately. Those keep `{ triggerTurn: true }`. Only *background notifications* get the `nextTurn` treatment.

## Distinguishing rule

Notification = informational, no action required → `{ deliverAs: "nextTurn" }`.
Instruction = must trigger the agent to act → `{ triggerTurn: true }`.

## Note

Takes effect on next session reload (extensions load at session start).
