# Plugins

Installing and managing Omarchy shell plugins.

## Installing a third-party plugin from a GitHub URL

**Symptom:** Want a community shell plugin (e.g. daniel-marr/omarchy-plugin-omafilee, which needs the Filee CLI from the KnifeLemon/Filee release tarball `install.sh` into ~/.local/bin/filee).

**Fix:**
1. Read the repo README Requirements first; install external CLI deps. Verify release checksums (`sha256sum -c`) before running any installer.
2. Review the code before enabling — plugins run unsandboxed inside the long-lived omarchy-shell process. Clone to /tmp and grep QML/JS for `Process`, `command`, `execDetached`, `hyprctl`, `curl`, `bash -c`. Compare against README claims. Delete the clone afterwards.
3. `omarchy plugin add <url> --enable --yes` — without `--yes` it prints a trust warning and exits 1. Only pass `--yes` after the review.
4. `omarchy plugin list | grep <name>` should show `enabled`.
5. `omarchy restart shell`, then `quickshell log -p /usr/share/omarchy/shell | grep <plugin>`. "Module path ... is outside of the config folder" is harmless for third-party plugins.

**Facts:** Plugins live in `~/.config/omarchy/plugins/<author>.<name>`. Remove with `omarchy plugin remove <id>`; if it registered runtime Hyprland rules also run `hyprctl reload`. Move a bar widget with `omarchy bar move <id> --section <section>`. `hyprctl` failing with "HYPRLAND_INSTANCE_SIGNATURE not set" from a detached context means the check is unverifiable there, not that the plugin is broken.

_Migrated from: omarchy-third-party-plugin-install_
