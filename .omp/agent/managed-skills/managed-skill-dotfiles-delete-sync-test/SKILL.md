---
name: managed-skill-dotfiles-delete-sync-test
description: Test skill to verify the managed-skill-dotfiles extension syncs create and delete with the wbrous-dev-ai co-author.
---

# managed-skill-dotfiles-delete-sync-test

Test skill created after the session reload that loads the OMPCODE=1-shell-prefix
+ delete-sync version of the `managed-skill-dotfiles` extension.

Expected (all by the extension, no manual git):
1. create  -> auto-commit `Add managed-skill: managed-skill-dotfiles-delete-sync-test`
   with `Co-authored-by: wbrous-dev-ai`.
2. delete  -> auto-commit `Remove managed-skill: managed-skill-dotfiles-delete-sync-test`,
   dropping the file from dotfiles HEAD.
