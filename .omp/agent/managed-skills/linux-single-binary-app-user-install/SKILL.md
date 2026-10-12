---
name: linux-single-binary-app-user-install
description: "Use when installing a downloaded standalone Linux ELF binary (no bin/lib/share bundle, no installer, no .desktop) from ~/Downloads and the user wants a launcher/desktop shortcut; e.g. Tern terminal. Prefer user-local install and check for a built-in register subcommand before hand-writing a .desktop file."
---

## When
User drops a lone executable (e.g. `Tern-0.8.2-linux-x86_64/tern/tern`, a ~160MB stripped ELF) and says "install it, make a desktop shortcut and everything". No .desktop/icons shipped. (If the archive ships a bundle with a .desktop, use `linux-manual-app-bundle-install` instead.)

## Steps (no sudo needed)
1. Inspect: `file <bin>`, `ldd <bin> | grep 'not found'`, `<bin> --help | head -60`, `<bin> --version`. Do NOT try to read the binary itself (huge).
2. Look in `--help` for a self-registration subcommand (`register`, `install`, `desktop-integration`). Tern has `tern register`, which writes the .desktop files, MIME associations and hicolor icons itself.
3. Install to a stable path BEFORE registering, because the generated .desktop hardcodes the path of the running binary in `Exec=`:
   `mkdir -p ~/.local/opt/<app> ~/.local/bin && cp <bin> ~/.local/opt/<app>/<app> && chmod +x ... && ln -sf ~/.local/opt/<app>/<app> ~/.local/bin/<app>`
   (Never register from ~/Downloads: Exec would point at a deletable location.)
4. Run `<app> register`. Verify: `desktop-file-validate ~/.local/share/applications/<id>.desktop`, `find ~/.local/share/icons -name '<id>*'`.
5. If the app has no register command: write `~/.local/share/applications/<name>.desktop` by hand (see existing ones there, e.g. Alacritty.desktop, for style), with Exec/Icon/StartupWMClass/Categories, and run `update-desktop-database ~/.local/share/applications`.
6. Optional literal desktop icon: `cp the .desktop ~/Desktop/ && chmod +x`. Machine is Hyprland/Omarchy, so skip unless asked.

## Gotchas
- `gtk-update-icon-cache` warning "generated cache was invalid" is harmless: ~/.local/share/icons/hicolor has no index.theme.
- `register` may claim file-type/MIME handlers (text, source, images, folders); tell the user and mention the `unregister` undo.
- Warn the user if help text mentions account sign-in / closed beta.
- Tell the user the Downloads dir can be deleted after copying.
