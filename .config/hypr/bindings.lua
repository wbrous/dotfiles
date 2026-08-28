-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, { omarchy = "walker -m symbols" })

-- Disable Omarchy defaults that collide with personal app choices below.
hl.unbind("SUPER + SHIFT + ALT + M") -- was "Music TUI" (cliamp)
hl.unbind("SUPER + SHIFT + M")       -- was "Music" (Spotify)
hl.unbind("SUPER + SHIFT + G")       -- was "Signal"
hl.unbind("SUPER + SHIFT + SLASH")   -- was "Passwords" (1Password)
hl.unbind("SUPER + SHIFT + E")       -- was "Email" (hey.com webapp)

-- Personal app bindings (migrated from bindings.conf).
-- Terminal, Tmux, Browser (+private), File manager (+cwd), Editor, Docker, and
-- Obsidian are covered by Omarchy defaults already and were dropped as duplicates.
o.bind("SUPER + SHIFT + M", "Music", "omarchy-launch-or-focus cider")
o.bind("SUPER + SHIFT + ALT + M", "Pulsemeeter", 'omarchy-launch-or-focus ^pulsemeeter$ "uwsm-app -- pulsemeeter"')
o.bind("SUPER + SHIFT + G", "Discord", 'omarchy-launch-or-focus ^discord$ "uwsm-app -- discord"')
o.bind("SUPER + SHIFT + SLASH", "Passwords", 'omarchy-launch-or-focus ^bitwarden$ "uwsm-app -- bitwarden-desktop"')
o.bind("SUPER + SHIFT + ALT + SLASH", "Passwords (2fa)", 'omarchy-launch-or-focus ^ente$ "uwsm-app -- enteauth"')
o.bind("SUPER + SHIFT + E", "Email", 'omarchy-launch-or-focus ^thunderbird$ "uwsm-app -- thunderbird"')

-- Default "dismiss most recent popup" is superseded by the two below.
hl.unbind("SUPER + comma") -- was "Dismiss last notification"

-- Clear the 3 visible toasts and immediately show queued ones (no snooze).
o.bind("SUPER + CTRL + comma", "Clear notifications", "omarchy-shell -q notifications dismissAll")

-- Right-click-a-toast equivalent: snooze new notifications and clear all.
o.bind("SUPER + SHIFT + comma", "Snooze & clear notifications", "omarchy-shell -q notifications snoozeAndClear")
