---
name: nextturn-delivery-test
description: "Throwaway skill to confirm the managed-skill-dotfiles extension delivers auto-commit notifications alongside the next user turn (nextTurn, no triggerTurn)."
---

# nextturn-delivery-test

Throwaway skill to verify the `managed-skill-dotfiles` extension now delivers its
auto-commit notification via `deliverAs: "nextTurn"` (no `triggerTurn`), so it
rides along with the next real user message instead of spawning a standalone
token-costing turn.

Expected: creating this skill auto-commits it to dotfiles and the confirmation
arrives as a system message with the next user turn, not as an immediate
separate turn.
