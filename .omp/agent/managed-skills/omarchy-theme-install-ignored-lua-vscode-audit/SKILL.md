---
name: omarchy-theme-install-ignored-lua-vscode-audit
description: "omarchy-theme-install prints \"Ignored in ...: neovim.lua vscode.json\"; audit then enable denied Lua/terminal/vscode.json files from a git-installed theme."
---

## Why files are ignored
`omarchy-theme-install <git-url>` clones to `~/.config/omarchy/themes/<name>` then runs `omarchy-theme-set`.
In `/usr/share/omarchy/bin/omarchy-theme-set`, `theme_came_from_a_repo` = non-symlink dir containing `.git`.
Such themes have denied: any `*.lua`, `alacritty.toml foot.ini ghostty.conf kitty.conf vscode.json`, and any symlinks. Everything else (colors, css, backgrounds) is staged.
Themes without `.git` are copied wholesale (`cp -r`).

## Recipe (only when user asks to verify/install the ignored files)
1. Read the ignored files in `~/.config/omarchy/themes/<name>/` (`cat`).
2. Audit:
   - `neovim.lua`: check it's only a lazy.nvim spec (plugin + `LazyVim` colorscheme opts). Clone each referenced plugin to /tmp, list files, grep for `os.execute|io.popen|vim.fn.system|vim.system|jobstart|vim.loop|vim.uv|curl|wget|loadstring|load(|ffi|nvim_exec`. Confirm author is the official one.
   - `vscode.json`: `{name, extension}`; `omarchy-theme-set-vscode` runs `<editor> --install-extension <id>` (arbitrary JS). Verify extension exists on Marketplace (web_search) and note publisher; check which editors are installed (`which code codium cursor`).
   - Terminal configs / hyprland.lua / gum_env.lua: these run code at login/terminal launch; read fully before enabling.
3. Confirm repo HEAD == origin/HEAD (`git fetch; git rev-parse HEAD origin/HEAD`).
4. Enable: write audited hashes to `<theme>/.audited-source`, `rm -rf <theme>/.git`, rerun `omarchy-theme-set <name>`. No "Ignored" warning should print; files appear in `~/.local/state/omarchy/current/theme/`.
5. Smoke test nvim: `nvim --headless "+lua vim.defer_fn(function() pcall(vim.cmd,'colorscheme X'); print(vim.g.colors_name, vim.inspect(vim.api.nvim_get_hl(0,{name='Normal'}))); vim.cmd('qa!') end, 15000)" | tail`. Pipe through `tail` (lazy clone progress is very noisy). `~/.config/nvim/lua/plugins/theme.lua` symlinks to current theme's neovim.lua.

## Tell the user
- Removing `.git` stops upstream updates; re-audit before updating.
- Neovim plugin is unpinned (suggest `commit = "<audited sha>"`).
- Extension author may differ from the plugin author; contents not audited unless actually reviewed.
- Reinstalling via `omarchy-theme-install` does `rm -rf` of the theme dir and re-clones, undoing this.
