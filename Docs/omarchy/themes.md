# Themes

Omarchy theme backgrounds, cursors, Qt styling, theme-set hooks, and installing third-party themes safely.

## Adding a wallpaper to a theme and fitting the display

**Symptom:** A wallpaper added to a theme (e.g. Ristretto) is cropped on a non-16:9 display.

**Cause:** System themes live in root-owned `/usr/share/omarchy/themes/<theme>/backgrounds/` (overwritten on update) — don't write there. The renderer (`/usr/share/omarchy/shell/plugins/background/Background.qml`) uses `Image.PreserveAspectCrop`: a 16:9 image on a 3:2 panel loses its SIDES. Put user images in `~/.config/omarchy/backgrounds/<theme>/` (mkdir -p); `omarchy-theme-bg-next` and `omarchy-theme-set` scan both dirs. Current theme: `cat ~/.local/state/omarchy/current/theme.name`. Apply with `omarchy theme bg next` or `omarchy-theme-bg-set <path>`. Copy, don't move, from ~/Downloads.

**Fix — pad instead of crop:** scale to panel width, extend height with the image's flat background colour. Get the resolution without hyprctl (fails outside Hyprland; `-j` can print binary garbage): `cat /sys/class/drm/card*-eDP-1/modes | head -1` (first line = preferred; e.g. 2880x1920 3:2).
```sh
magick img.png -format "%[pixel:p{5,5}]\n" info:   # must be flat, e.g. srgb(40,40,40) = #282828
magick src.png -resize 2880x -background '#282828' -gravity center -extent 2880x1920 out.png
magick out.png -resize 1200x /tmp/preview.png   # separate command, then view to verify
```
Only works cleanly on flat-colour backgrounds; otherwise ask about crop vs. blur-fill.

_Migrated from: omarchy-add-theme-background-fit-display_

## Reset cursor after an accent/recolor plugin

**Symptom:** Wrong cursor remains after uninstalling a theme-recoloring cursor plugin (Omarchy-Accent, cursor-accent).

**Cause:** Plugin leftovers: generated themes under `~/.local/share/icons` (e.g. `Omarchy-Accent` with hyprcursors/, `Inherits=Adwaita`) and state under `~/.local/state` (e.g. `cursor-accent/render.json`). Defaults for reference: login cursor from `env | grep -E 'OMARCHY_STARTUP_CURSOR|XCURSOR'` is theme `default`, size 24; `/usr/share/icons/default/index.theme` is `Inherits=Adwaita`; stock config in `/usr/share/omarchy/default/hypr/envs.lua` (size 24) and `startup-cursor.lua`.

**Fix:**
```sh
ls ~/.local/share/icons; ls ~/.local/state | grep -i cursor   # find leftovers; check timestamps before blaming a tool
# also grep ~/.config/hypr, ~/.config/omarchy/hooks/theme-set.d, gtk settings.ini,
# gsettings get org.gnome.desktop.interface cursor-theme
```
1. Move (not delete) leftover theme + state dirs to `~/.local/state/cursor-accent-removed-<ts>/`.
2. `hyprctl setcursor default 24`
3. `gsettings set org.gnome.desktop.interface cursor-theme 'default'` and `cursor-size 24`.
4. Already-open apps may cache the cursor: reopen or relogin.

_Migrated from: omarchy-cursor-reset-after-accent-plugin_

## Kvantum was deliberately removed — do not reinstall

**Symptom:** Qt/QML apps (e.g. hyprpolkitagent fingerprint/polkit dialog) look plain after an update; `kvantum`/`kvantum-qt5` missing.

**Cause:** Intentional. Migration `1785351479.sh` (`~/.local/share/omarchy/migrations/` or `/usr/share/omarchy/migrations/`) runs `pacman -Rns kvantum-qt5 kvantum`. Omarchy never shipped a `.kvconfig`, `QT_STYLE_OVERRIDE` is gone, and Qt apps now theme via `QT_QPA_PLATFORMTHEME=gtk3`. Reinstalling or adding a pacman hook fights the migration (explicit `pacman -Rns` overrides hooks) — tried and reverted in a real session.

**Fix:** Real styling for `hyprpolkitagent` comes from `hyprland-qt-support` (custom QML controls at `/usr/lib/qt6/qml/org/hyprland/style/` reading theme colors directly):
```sh
grep -A5 kvantum ~/.local/share/omarchy/migrations/*.sh
pacman -Qi kvantum 2>&1                  # "not found" is correct
pacman -Qi hyprland-qt-support           # must be installed, Required By: hyprpolkitagent
systemctl --user restart hyprpolkitagent.service
```
If still wrong with Kvantum absent, look at stale QML cache / QQC2 style env / agent restart — not a missing theme engine. Migration leaves `qt5-wayland`/`qt5-declarative` alone (legacy SDDM greeters need them).

_Migrated from: omarchy-kvantum-dropped-for-gtk3-theming_

## Weather widget unit (Celsius/Fahrenheit)

**Symptom:** Bar weather widget shows the wrong unit.

**Cause:** Default is locale/country detection (`shouldUseImperial` in `/usr/share/omarchy/shell/plugins/panels/weather/Model.js`).

**Fix:** Edit `~/.config/omarchy/shell.json`, find the `"id": "omarchy.weather"` layout entry, add `"unit": "metric"` (Celsius) or `"unit": "imperial"` (Fahrenheit). No restart — `shell.json` hot-reloads; validate JSON after editing (`python3 -c "import json;json.load(open(path))"`).

**Pitfall:** Do NOT run `omarchy restart shell` after this edit — the bar's drag-reorder autosave (`mutateShellConfig` in `plugins/bar/Bar.qml`) can re-serialize the layout and silently strip the `"unit"` key. Save, wait a couple seconds for hot-reload, re-read the file to confirm the key stuck.

_Migrated from: omarchy-weather-unit_

## Installing a git theme: "Ignored in ...: neovim.lua vscode.json"

**Symptom:** `omarchy-theme-install <git-url>` prints `Ignored in ...: neovim.lua vscode.json`.

**Cause:** In `/usr/share/omarchy/bin/omarchy-theme-set`, `theme_came_from_a_repo` = non-symlink dir containing `.git`. Such themes deny: any `*.lua`, `alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json`, and any symlinks. Themes without `.git` copy wholesale.

**Fix (only when the user asks to verify/install the ignored files):**
1. Read the ignored files in `~/.config/omarchy/themes/<name>/`.
2. Audit: `neovim.lua` must be only a lazy.nvim spec — clone each referenced plugin to /tmp, list files, grep for `os.execute|io.popen|vim.fn.system|vim.system|jobstart|vim.loop|vim.uv|curl|wget|loadstring|load(|ffi|nvim_exec`; confirm author is official. `vscode.json` is `{name, extension}`; `omarchy-theme-set-vscode` runs `<editor> --install-extension <id>` — verify the extension on the Marketplace, note publisher, check installed editors (`which code codium cursor`). Terminal configs / hyprland.lua / gum_env.lua run code at login/terminal launch — read fully.
3. `git fetch; git rev-parse HEAD origin/HEAD` — confirm HEAD == origin/HEAD.
4. Write audited hashes to `<theme>/.audited-source`, `rm -rf <theme>/.git`, rerun `omarchy-theme-set <name>`. No "Ignored" warning; files land in `~/.local/state/omarchy/current/theme/`.
5. Smoke-test nvim headless (pipe through `tail`; lazy clone output is noisy): `nvim --headless "+lua vim.defer_fn(function() pcall(vim.cmd,'colorscheme X'); print(vim.g.colors_name, vim.inspect(vim.api.nvim_get_hl(0,{name='Normal'}))); vim.cmd('qa!') end, 15000)" | tail`. `~/.config/nvim/lua/plugins/theme.lua` symlinks to the current theme's neovim.lua.

Tell the user: removing `.git` stops upstream updates (re-audit before updating); the nvim plugin is unpinned (suggest `commit = "<audited sha>"`); extension author may differ from plugin author; reinstalling via `omarchy-theme-install` does `rm -rf` + re-clone, undoing this.

_Migrated from: omarchy-theme-install-ignored-lua-vscode-audit_

## sudo installers managing user systemd units

**Symptom:** An installer with header `omarchy:requires-sudo=true` (runs as root) must enable/disable `systemctl --user` units.

**Cause:** Two bugs: (1) sudo wipes `$DBUS_SESSION_BUS_ADDRESS`/`$XDG_RUNTIME_DIR`, so bare `systemctl --user ...` as root fails with `Failed to connect to user scope bus via local transport`; (2) `systemctl --user enable` is a no-op if the unit file only exists in the repo — copy to `~/.config/systemd/user/` first (omarchy's `default/systemd/user/` convention: `install`, not symlink).

**Fix:**
```bash
user=${SUDO_USER:-$USER}
runtime=/run/user/$(id -u "$user")
unit_dir=/home/$user/.config/systemd/user
sudo -u "$user" mkdir -p "$unit_dir"
for unit in foo.service bar.service; do
  sudo install -o "$user" -g "$user" -m 644 "$SRC/default/systemd/user/$unit" "$unit_dir/$unit"
done
sudo -u "$user" XDG_RUNTIME_DIR=$runtime systemctl --user daemon-reload
sudo -u "$user" XDG_RUNTIME_DIR=$runtime systemctl --user enable foo.service bar.service
```
Remover mirrors it: `disable --now` as `$user`, then `sudo -u "$user" rm -f ...`, plus root-owned pieces with `sudo rm -f`. Use `$runtime`, not `${XDG_RUNTIME_DIR:?}` (root's is unset). Verify with `bash -n` + `shellcheck -S warning`, dry-run the deploy loop into `mktemp -d`.

_Migrated from: omarchy-sudo-installer-user-units_
