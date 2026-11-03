---
name: msi-1603-install-log-missing-vcruntime
description: MSI install fails with 1603 in a clean Windows VM; custom action returns -1073741515 (0xC0000135); fetch and read install.log from a libvirt VM; Rust exe needs static CRT.
---

# MSI 1603 on a clean Windows VM: read the log, find the cause

## Getting install.log out of a libvirt Windows VM

Offline disk access is usually a dead end: no sudo, no NTFS userspace reader, no guest agent.
Use the network instead. `virsh -c qemu:///system domifaddr <vm>` gives the IP. Ask the user to run, in the folder holding the log (elevated PowerShell):

```powershell
python -m http.server 8000      # or an HttpListener loop if Python is absent
New-NetFirewallRule -DisplayName "tmp-8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Then `curl -o install.log http://<ip>:8000/install.log`. Afterwards: `Remove-NetFirewallRule -DisplayName "tmp-8000"`.

## Reading it

`msiexec /l*v` logs are UTF-16LE: `iconv -f UTF-16LE -t UTF-8 install.log | tr -d '\r' > install.txt`.
Ignore the many `Note: 1: 2205` / `2262` lines (benign missing-table notes). Look at:

- `MainEngineThread is returning 1603` (the overall result)
- `Action ended ...: InstallFinalize. Return value 3`
- `CustomAction <Id> returned actual error code <N>` just before it. Hidden properties (pairing codes) show as `**********`.

## 0xC0000135 / -1073741515

`STATUS_DLL_NOT_FOUND`: the exe a custom action runs could not start. For a Rust MSVC exe it is
`VCRUNTIME140.dll` / `api-ms-win-crt-*` missing on a stock Windows. A `Return="check"` action fails the
install and rolls it back; a `Return="ignore"` action hides it (e.g. a driver that never registers).

Fix: link the CRT statically in `.cargo/config.toml`:

```toml
[target.'cfg(all(windows, target_env = "msvc"))']
rustflags = ["-C", "target-feature=+crt-static"]
```

Guard it in the build script with `dumpbin /dependents optic.exe` (found via vswhere under
`VC\Tools\MSVC\**\bin\Hostx64\x64\`) and fail on `VCRUNTIME*|MSVCP*|api-ms-win-crt-*`.
To check a shipped exe from Linux: `7z x installer.msi -ox` extracts the files, then read the PE import table.
Local mingw (`gnu`) builds are unaffected by the `msvc`-scoped cfg.

## Related

Signing the commit that carries the fix needs a fingerprint touch: see `git-commit-gpg-fingerprint-timeout-retry`.
