# GitHub, GitLab, and CI

gh/glab CLIs, PAT scopes, GitLab stuck-MR recovery, and CI build recipes.

## Bulk GitHub issues + Projects v2 fields

**Prereqs:** `gh auth refresh -s read:project,project -h github.com` (interactive device flow) before any `gh project` command.

**IDs:** `gh project view <NUM> --owner <ORG> --format json | jq -r '.id'` (node ID `PVT_...`); `gh project field-list <NUM> --owner <ORG> --format json` for field + option IDs. Create a missing single-select: `gh project field-create <NUM> --owner <ORG> --name "Priority" --data-type SINGLE_SELECT --single-select-options "P0,P1,P2"`. No CLI edits options on an existing field — use the `updateProjectV2Field` GraphQL mutation (replaces the entire option list; people without GitHub accounts are valid option values).

**Bulk flow:** per issue `gh issue create -R <repo> -t -b -l -a` → capture URL → `gh project item-add <NUM> --owner <ORG> --url "$url"` → `item-edit --field-id --single-select-option-id`. Wrap add/edit in 3–5× retry (`sleep 2`): transient `TLS handshake timeout` / `Content already exists` under batch load. Off-by-one trap when resuming from a slice — after the run, diff created titles vs source list (`diff <(jq titles source) <(gh issue list --json title ...)`). Rename-to-tag reads priority back from each issue's own labels, then `gh issue edit <num> -R <repo> -t "[P0 FEAT] ..."`. Bulk status moves: `gh project item-list <NUM> --owner <ORG> --format json --limit 100` exposes custom fields flattened (`.priority`, `.status`) — `jq` filter + loop `item-edit`, verify with `sort | uniq -c`.

_Migrated from: github-gh-cli-bulk-issue-and-projectv2-priority-seed_

## PAT scope model and tracked-env-secret trap

Classic PATs (`ghp_...`) are coarse: `repo` = contents+issues+PRs together; there is NO classic scope granting PR-write without contents-write — a "pull_request: write only" claim on a classic PAT is false (only calling code, not the token, enforces it). Per-resource splits exist only on fine-grained PATs (Settings → Developer settings, or org PAT-approval admin API). Design docs must name fine-grained explicitly.

Before `git status`/`commit` in fresh scaffolds, check whether `.env` (not just `.env.example`) is tracked — a committed placeholder `.env` becomes a credential commit the moment real values are filled and `git commit -a` runs. Fix: `git rm --cached .env`, add to `.gitignore`, commit separately. If real secrets were visible in a diff/output (even uncommitted), tell the user to rotate them.

_Migrated from: github-pat-scope-model-pitfalls_

## Bare-clone mirror sync goes stale / GitLab push mirror stuck

**Symptom:** `git fetch origin` in a `--bare` clone prints only `* branch HEAD -> FETCH_HEAD`; `git rev-parse main dev` stays stale though the remote moved — then a force-push to a second remote silently regresses it.

**Cause:** bare clone's default fetch refspec doesn't update local `refs/heads/*` on a bare `git fetch origin`.

**Fix:** never trust bare-clone refs after a bare fetch — re-verify with `git ls-remote <source-url>` vs `git rev-parse`. Safest: delete and re-clone `--bare` fresh before each sync push. Confirm with `ls-remote` on both sides after pushing. Stuck self-hosted (Docker gitlab-ee) push mirror (`update_status: finished` but `last_update_at` older than your push): trigger manually `glab api -X POST projects/:id/remote_mirrors/:mirror_id/sync`; still stuck → `docker exec -it gitlab-ee gitlab-ctl restart sidekiq`. Still need it now → bypass the mirror with a fresh `--bare` clone + `git push <dest> b1:b1 b2:b2 --force --porcelain`, verify via `ls-remote` both sides.

_Migrated from: gitlab-bare-clone-fetch-stale-refs-mirror-fix_

## Force-push a protected GitLab branch via API

**Symptom:** `remote: GitLab: You are not allowed to push code to protected branches` / pre-receive hook declined — a protection rule (`push_access_level` "No one"), not auth.

**Fix:**
```sh
glab api "projects?search=<repo>&membership=true" --hostname <host>   # numeric id + path_with_namespace
glab api "projects/<id>/protected_branches" --hostname <host>          # record current rule
glab api "projects/<id>/protected_branches/<branch>" --method DELETE --hostname <host>
git push origin <branch> --force
glab api "projects/<id>/protected_branches" --method POST --hostname <host> \
  -f name=<branch> -f push_access_level=<N> -f merge_access_level=<N> -f allow_force_push=<bool>
```
Levels: 0=No one, 30=Developers, 40=Maintainers, 60=Admins. Merging branches into main first: check divergence both directions (`git log --oneline A..B | wc -l`) then sequential `git merge origin/<branch>`; require `git log --oneline origin/main..origin/<branch> | wc -l` = 0 for every branch before pushing. Gotcha: `glab auth status` may fail on an unrelated gitlab.com token while the self-hosted host is fine — read the per-host block.

_Migrated from: gitlab-force-push-protected-branch-via-api_

## GitLab MR stuck "preparing" + 405 (Sidekiq backlog)

**Symptom:** merge button hangs "Your merge request is almost ready!"; API shows `merge_status: checking`, `detailed_merge_status: preparing`, `prepared_at: None` indefinitely; `glab mr merge` / `PUT .../merge` → `405 Method Not Allowed`. Draft/conflicts/discussions/approvals all fine.

**Cause:** stuck server-side MR-prepare worker (Sidekiq backlog), not client-fixable. Retries, `GET changes`, `glab mr update` nudges, and no CLI flag bypass it.

**Fix (self-hosted, needs instance admin):**
```sh
docker exec -it gitlab-ee gitlab-ctl restart sidekiq
```
Wait ~15–30s, re-check merge_status via the API. Brief GitLab slowness (SSH/API timeouts) right after is normal load — wait 1–2 min; a merge-on-success MR often auto-merges once Sidekiq catches up. Deeper diagnosis (`gitlab-rails runner` Sidekiq queue sizes) costs a 30–90s cold Rails boot — normal.

Safety before any "force-push X onto main": verify ancestry first — `git log --oneline main..<branch> | wc -l`, reverse, and `git merge-base --is-ancestor <branch> main`. If 0 and ancestor, main is already ahead; report instead of pushing. Check push-mirror health via `glab api projects/<owner>%2F<repo>/remote_mirrors` (`update_status: finished`, `last_error: null`, recent `last_successful_update_at`).

_Migrated from: gitlab-mr-merge-stuck-preparing-405, gitlab-mr-stuck-preparing-fix-sidekiq-restart_

## KMDF driver build on GitHub Actions (WDK via NuGet)

`ntddk.h` not found: the runner has the VS WDK extension but not headers/libs. Restore from NuGet like microsoft/Windows-driver-samples: `packages.config` with `Microsoft.Windows.SDK.CPP`, `.CPP.x64`, `.WDK.x64` all the same version; `nuget restore packages.config -PackagesDirectory packages` (fetch nuget.exe from dist.nuget.org); `Directory.Build.props` importing the three `.props` files when `Exists()` and `$(Platform)=='x64'`. Never `dotnet restore`/`dotnet build` for WDK (per Microsoft) — nuget.exe + msbuild. Link note: `SDDL_DEVOBJ_SYS_ALL_ADM_ALL` needs `wdmsec.lib` in `Link/AdditionalDependencies`.

`MSB4062 ValidateNTTargetVersion ...Tasks.18.0.dll`: MSBuild must match the WDK's build-task DLL. `windows-2025-vs2026` = VS2026 = MSBuild 18.0, needs `...Tasks.18.0.dll`; WDK `10.0.26100.x` ships only `17.0` → pin WDK/SDK to `10.0.28000.x` AND `runs-on: windows-2025-vs2026` so `windows-latest` can't drift. Check candidates: `unzip -l <pkg>.nupkg | grep Build.Tasks`. Caveat: the 28000.x pin was evidence-chosen but not yet green-confirmed when written — read the next error from `gh run view <id> --log-failed`. Not worth trying: clang-cl syntax-checking on Linux (header casing, DriverSpecs.h rabbit hole). Signing still required (test-signing or attestation).

_Migrated from: kmdf-driver-github-actions-wdk-nuget_

## Flutter release via workflow_dispatch

Scaffold with `flutter create --platforms=android,ios --org <org> --project-name <name> .` (delete `*.iml`). `.github/workflows/release.yml`: `on: workflow_dispatch` with boolean `prerelease` input; `version` job parses `pubspec.yaml` (`sed -nE 's/^version:[[:space:]]*([^[:space:]#]+).*/\1/p'`), validates `^[0-9]+\.[0-9]+\.[0-9]+(\+[0-9]+)?$`, outputs `v<version>`, fails if the tag exists (`git ls-remote --exit-code --tags origin refs/tags/$TAG`); `build-android` (ubuntu, setup-java 17 temurin, subosito/flutter-action@v2: pub get, analyze, test, `flutter build apk --release`); `build-ios` (macos-latest: `flutter build ios --release --no-codesign`, `mkdir Payload; cp -R build/ios/iphoneos/Runner.app Payload/; zip -qry x.ipa Payload`); `release` job (`permissions: contents: write`): `download-artifact merge-multiple: true` into `dist`, `gh release create "$TAG" dist/* --target "$GITHUB_SHA" --generate-notes [--prerelease]`. Top-level `permissions: contents read`; pass inputs via `env:`. Local builds may be impossible (Android cmdline-tools/licenses, iOS needs macOS) — say so; artifacts are unsigned (Android debug key, iOS `--no-codesign`) — document it; repo may need `git init` + push before the workflow appears; don't add unrequested extra workflows.

_Migrated from: flutter-github-release-workflow-dispatch_
