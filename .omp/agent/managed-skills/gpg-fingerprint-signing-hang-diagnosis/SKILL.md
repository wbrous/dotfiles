---
name: gpg-fingerprint-signing-hang-diagnosis
description: "Diagnose git GPG fingerprint-signing hangs: stale pinentry lock vs live prompt waiting on user scan"
---

# GPG Fingerprint Signing Hang Diagnosis

When `git commit -S` / `git tag -s` hangs waiting on a fingerprint-gated
pinentry (e.g. `pinentry-fprintd` + `pkexec`), don't retry blindly. Diagnose:

1. `ps -eo pid,etimes,args | grep -E "[p]inentry-fprintd|[g]pg-fingerprint-read"`
   - A live `pkexec ...gpg-fingerprint-read` pid means a real polkit prompt is
     pending: the dialog is on the user's screen and only their finger scan
     unblocks it. Give it ~40s, then ask the user whether any dialog appeared.
   - An old pid (>5 min, surviving its parent attempt) is a stale lock holder
     from a previous timed-out attempt. Kill it: `pkill -f pinentry-fprintd;
     pkill -f gpg-fingerprint-read`, then `gpgconf --kill gpg-agent` and retry.
2. `journalctl --user --since "-3min" | grep -iE "gpg-agent|pinentry"`:
   `failed to acquire the pinentry lock: Timeout` confirms a stale holder.
3. If the prompt is live but the user reports NO dialog on screen, the polkit
   agent is the suspect, not GPG: check `systemctl --user is-enabled
   hyprpolkitagent` and whether the desktop's own agent registered (e.g.
   omarchy's `omarchy polkit agent registered` in shell logs). See
   `omarchy-polkit-agent-vs-hyprpolkitagent`.
4. Never stack retries: each timed-out attempt leaves another stale holder,
   making the next attempt hang too. One attempt, one diagnosis, one cleanup.
