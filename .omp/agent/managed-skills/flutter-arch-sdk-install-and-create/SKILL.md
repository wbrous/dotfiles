---
name: flutter-arch-sdk-install-and-create
description: "Use when Flutter is missing on Arch/Omarchy (no flutter in pacman, sudo needs password) and you must scaffold a Flutter app."
---

# Flutter SDK install and app scaffold on Arch (no sudo)

## Findings
- `flutter` is NOT in the official pacman repos (only `fvm`, which needs sudo). `yay -Ss flutter` returns unrelated AUR apps.
- `sudo -n` fails when a password is required, so avoid pacman installs.

## Recipe
1. Clone the SDK without sudo:
   `git clone --depth 1 -b stable https://github.com/flutter/flutter.git ~/development/flutter`
2. Use it per command (PATH is not persisted):
   `export PATH="$HOME/development/flutter/bin:$PATH"`
3. Scaffold into the current (empty) directory:
   `flutter create --platforms=android,ios --org <org> --project-name <name> .`
   - First run downloads the Dart SDK and takes about 60s. The tool call may background, so wait for it instead of polling.
   - Project names must be valid Dart identifiers.
4. Verify: `flutter analyze` and `flutter test` (the template includes a counter widget test).

## Notes
- Tell the user to add the PATH export to their shell config.
- iOS builds require macOS and Xcode. Android builds need the Android SDK; `flutter doctor` lists what is missing.
- Ask the user about platforms and app scope before scaffolding. Do not assume defaults.
