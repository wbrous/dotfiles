---
name: cider-remove-broken-plugin
description: "Cider (Apple Music client) plugin broken or won't uninstall from the UI; remove it manually from disk on Linux."
---

## Cider plugin manual removal (Linux)

Use when a Cider plugin (e.g. Cider Audio Labs / "CiderAudio Expanded") is broken and the in-app uninstall fails.

Facts (verified on Arch, cider 4.0.9.1 from pacman):
- User data dir: `~/.config/sh.cider.genten` (the `~/.config/Cider` dir is separate). Confirm via `--user-data-dir=` in `pgrep -a Cider`.
- Plugins live in `~/.config/sh.cider.genten/plugins/<identifier>/` with a `plugin.yml` (`identifier`, `name`, `marketplaceID`) and `plugin.js`.
- Audio Labs identifier is `sh.cider.audiolabs`; it also bundles `cideraudio/impulses/*.wav`.
- Plugin is NOT registered in `spa-config.yml` (grep showed no references), so deleting the folder is enough.

Steps:
1. `ls ~/.config/sh.cider.genten/plugins` and read the target's `plugin.yml` to confirm it's the right one.
2. Quit Cider first (`pkill -x Cider`, verify with `pgrep -x Cider`) so it can't recreate/lock the folder.
3. `rm -rf ~/.config/sh.cider.genten/plugins/<identifier>`.
4. Optionally grep `spa-config.yml` for the identifier; clean only if present.
5. Tell the user to relaunch; reinstall from the marketplace if wanted.
