---
name: managed-skill-dotfiles-autosync-test-2
description: Second verification skill to confirm the managed-skill-dotfiles extension auto-commits updated managed skills to dotfiles with the wbrous-dev-ai co-author trailer.
---

# managed-skill-dotfiles-autosync-test-2

Fresh end-to-end verification of the `managed-skill-dotfiles` omp extension
after reloading the session so the extension is loaded into the runtime.

If this skill automatically appears as a `git commit` in the `~/.dotfiles`
bare repo — message `Add managed-skill: managed-skill-dotfiles-autosync-test-2`
— the extension works. If it does not, the extension's `tool_result` hook is
not firing and the code is wrong.

This line was added by an UPDATE to verify the extension auto-commits updates
AND that the commit carries the `Co-authored-by: wbrous-dev-ai` trailer
(OMPCODE=1 propagation from the extension's bareGit helper).
