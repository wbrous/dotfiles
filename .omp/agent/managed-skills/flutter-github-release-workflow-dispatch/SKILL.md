---
name: flutter-github-release-workflow-dispatch
description: "Use when adding a manual (workflow_dispatch) GitHub Actions release for a Flutter app: version from pubspec.yaml, optional prerelease checkbox, Android APK + unsigned iOS IPA."
---

# Flutter release via workflow_dispatch

## Recipe
1. If Flutter is already on PATH (`flutter --version`), scaffold with `flutter create --platforms=android,ios --org <org> --project-name <name> .` in the empty dir. Delete the generated `*.iml`.
2. Write `.github/workflows/release.yml` with:
   - `on: workflow_dispatch` with input `prerelease` (`type: boolean`, default false).
   - Job `version`: parse `version:` from `pubspec.yaml` with
     `sed -nE 's/^version:[[:space:]]*([^[:space:]#]+).*/\1/p' pubspec.yaml`, validate with regex `^[0-9]+\.[0-9]+\.[0-9]+(\+[0-9]+)?$`, output tag `v<version>`, fail early if the tag exists (`git ls-remote --exit-code --tags origin refs/tags/$TAG`).
   - Job `build-android` (ubuntu, setup-java 17 temurin, `subosito/flutter-action@v2`): pub get, analyze, test, `flutter build apk --release`, upload artifact.
   - Job `build-ios` (macos-latest): `flutter build ios --release --no-codesign`, then `mkdir Payload; cp -R build/ios/iphoneos/Runner.app Payload/; zip -qry x.ipa Payload`, upload artifact.
   - Job `release` (`permissions: contents: write`): download-artifact `merge-multiple: true` into `dist`, then `gh release create "$TAG" dist/* --target "$GITHUB_SHA" --generate-notes [--prerelease]`.
   - Top-level `permissions: contents read`; job-level write only on release. Pass inputs via `env:`, not inline `${{ }}` in scripts.
3. Verify locally: `flutter analyze`, `flutter test`, YAML parses (PyYAML maps `on` to key `True`), run the sed against pubspec. `actionlint` is often not installed.

## Notes
- Local Android release builds may be impossible (missing cmdline-tools/licenses in `flutter doctor`); iOS needs macOS. Say so instead of claiming a build was tested.
- Artifacts are unsigned for distribution (Android uses debug key, iOS `--no-codesign`); tell the user and document it in README.
- Repo may not be a git repo yet; tell the user to `git init` and push before the workflow appears.
- Do not add extra workflows (e.g. CI) that were not requested.
