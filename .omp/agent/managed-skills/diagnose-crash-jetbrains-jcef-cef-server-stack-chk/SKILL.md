---
name: diagnose-crash-jetbrains-jcef-cef-server-stack-chk
description: "Repeated cef_server SIGABRT from JetBrains IDE (IntelliJ, PyCharm, Rider...) jcef-plugin, __stack_chk_fail in CefExecuteProcess, Unzipper/DataDecoder utility; coredump burst."
---

# JetBrains JCEF `cef_server` SIGABRT (`__stack_chk_fail`)

Use with the `diagnose-crash` skill when coredumpctl shows many `cef_server` aborts from `.../jcef-plugin/jcef/cef_server`.

## Fingerprint (all must match)
- Crash thread: `main -> CefExecuteProcess -> __stack_chk_fail -> __fortify_fail -> abort` (offsets seen: `cef_server+0x29f1b1`, `main+0x5a498`, JCEF `remote_144.0.15.3416`).
- Cmdline: `--type=utility --utility-sub-type=unzip.mojom.Unzipper` (also `data_decoder.mojom.DataDecoderService`, `on_device_model...`) with `--change-stack-guard-on-fork=enable --no-sandbox`.
- Bursts of dozens of cores within seconds; parent `cef_server --port=...`, GPU/network/renderer/zygote helpers and the IDE itself survive. No OOM, no data loss.
- Seen on glibc 2.39-2.44 (Arch/Omarchy, CachyOS, Ubuntu).

## Cause (confirmed by upstream reports, not by local symbolization)
JetBrains hardcodes `--change-stack-guard-on-fork=enable`; helpers trip the stack canary on glibc 2.39+. Unfixed as of 2026-10-31. Tracked in YouTrack: JBR-10670, JBR-10677, JBR-10549, PY-92855. NOT an Omarchy bug; do not file to Omarchy. Don't file a duplicate with JetBrains either; add a confirmation to JBR-10670.

## Efficient workflow
1. `coredumpctl list | grep -c cef_server`, check a few PIDs for same subtype. Skip gdb: JetBrains ships no symbols and debuginfod has none; frames stay unresolved (if you do extract a core, mktemp and delete it).
2. Rule out OOM (`free -h`, journal), then web_search the stack signature; YouTrack pages are JS-rendered, so use `curl -H 'Accept: application/json' 'https://youtrack.jetbrains.com/api/issues/JBR-10670?fields=idReadable,summary,description,customFields(name,value(name))'`.
3. Trigger is browser startup (e.g. Markdown preview, extension CRX unpack); do not blame the component updater or cache writes without evidence.

## User options (offer; don't apply unprompted)
- Disable JCEF: `-Dide.browser.jcef.enabled=false` in Help > Edit Custom VM Options (`~/.config/JetBrains/<IDE><ver>/idea64.vmoptions`). Stops crashes; loses Markdown preview and other browser panels. Reported by others; not tested locally.
- `-Dide.browser.jcef.sandbox.enable=false` reportedly does NOT help.
- Live with it, wait for fix, or `omarchy-crash-mute '<cef_server path>'` (keys on name `cef_server`; undo with `off`).
