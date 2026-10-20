---
name: omarchy-third-party-plugin-install
description: "Installing a third-party Omarchy shell plugin from a GitHub URL (omarchy plugin add); --yes confirmation, external CLI deps, verify after restart."
---

## Procedure

1. Read the repo README (Requirements section) for external dependencies, e.g. a CLI that must be on PATH. Install those first. Verify release checksums (`sha256sum -c`) before running any installer.
2. Review the plugin code before enabling: plugins run unsandboxed inside the long-lived omarchy-shell process. Clone to /tmp and grep QML/JS for `Process`, `command`, `execDetached`, `hyprctl`, `curl`, `bash -c`. Compare against what the README claims. Delete the clone afterwards.
3. Install: `omarchy plugin add <url> --enable --yes`
   - Without `--yes` it prints a trust warning and exits 1 ("refusing to continue without confirmation"). Only pass `--yes` after the review in step 2.
4. Verify: `omarchy plugin list | grep <name>` should show `enabled`.
5. `omarchy restart shell`, then check `quickshell log -p /usr/share/omarchy/shell | grep <plugin>`.
   - The warning "Module path ... is outside of the config folder" is harmless for third-party plugins.
   - `hyprctl` fails with "HYPRLAND_INSTANCE_SIGNATURE not set" when run from a context not attached to a Hyprland session. That means the check is unverifiable there, not that the plugin is broken.

## Facts

- Plugins live in `~/.config/omarchy/plugins/<author>.<name>`.
- Remove with `omarchy plugin remove <id>`. If the plugin registered runtime Hyprland rules, also run `hyprctl reload`.
- Move a bar widget with `omarchy bar move <id> --section <section>`.
- Example: daniel-marr/omarchy-plugin-omafilee needs the Filee CLI (KnifeLemon/Filee release tarball, `install.sh`, installs to ~/.local/bin/filee).
