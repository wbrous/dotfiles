---
name: zen-browser-userchrome-theme-install
description: "Install a userChrome/userContent CSS theme (e.g. catppuccin/zen-browser) into Zen Browser on Linux; find the right profile, enable legacy stylesheets."
---

## Steps
1. Find the active profile: read `~/.config/zen/installs.ini`. The `Default=` path under the `[Install...]` section is the profile the install is locked to. `profiles.ini` can list several profiles, and the one marked `Default=1` there may NOT be the active one.
2. In that profile, `chrome/` may already exist because Zen's mod manager creates it. It holds `zen-themes.css` and `zen-themes/`, which are regenerated, so don't edit or overwrite them. Add `userChrome.css`, `userContent.css` and any assets next to them.
3. Enable stylesheets by writing `user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);` to `<profile>/user.js`. Create the file if absent and append rather than overwrite. Zen applies it on startup. Zen's `prefs.js` is rewritten while the browser runs, so don't edit that.
4. Fetch theme files with `curl -fsSL` from `raw.githubusercontent.com/<repo>/main/...`. For catppuccin/zen-browser the path is `themes/<Flavor>/<Accent>/{userChrome.css,userContent.css,zen-logo-<flavor>.svg}`. Flavors are Latte, Frappe, Macchiato and Mocha. There are 14 accents, including Mauve and Blue. Check that the CSS references the logo filename you saved (`grep zen-logo`).
5. Tell the user to restart Zen, since it is usually running (`pgrep -a zen`). Latte needs light mode and the other flavors need dark mode. To follow the OS light/dark setting, concatenate the Latte CSS with a dark flavor's CSS.

## Notes
- Visual rendering can't be checked while Zen is running without a restart, so say so rather than claiming it works.
