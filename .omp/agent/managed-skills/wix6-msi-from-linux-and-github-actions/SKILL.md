---
name: wix6-msi-from-linux-and-github-actions
description: "Authoring a WiX 6 MSI (service, kernel driver, custom actions) and building it in GitHub Actions; WiX 7 EULA, WIX0389 on Linux, no stock UI without a licence."
---

# WiX 6 MSI: authoring and CI gotchas

## Version choice
- WiX 7 requires accepting the OSMF EULA (`-acceptEula wix7`); orgs over $10k revenue owe a fee. Do not accept it silently in CI. Pin WiX 6.0.2 (no EULA): `dotnet tool install --global wix --version 6.0.2`, then `wix extension add --global WixToolset.Util.wixext/6.0.2`.
- `windows-latest` ships only WiX 3.14, plus VS 2022 with the WDK VS extension and Windows SDK 26100, .NET 9 and Rust. No WDK install step needed for `WindowsKernelModeDriver10.0` projects.

## Local validation on Linux (limited)
- `wix` runs under `dotnet` on Linux but warns "undefined behavior". It still catches XML and schema errors, but EVERY `Directory/@Name` fails with WIX0389 (even a minimal file). Treat WIX0389 as a platform artifact, not a bug; a full MSI build is impossible there. Any other error is real.
- Check PowerShell syntax with `System.Management.Automation.Language.Parser.ParseFile` (NuGet `Microsoft.PowerShell.SDK`), and workflows with `actionlint`.

## Authoring facts (verified against docs/compiler)
- XML comments cannot contain `--` (e.g. CLI flags like `--server`).
- Windows Installer cannot `ServiceInstall` a kernel driver: copy the .sys in MSI, register it via a deferred custom action running the installed exe (SCM API).
- WiX 6 names: `FileRef` (not FileKey), `HideTarget` keeps secrets out of the log, `util:ServiceConfig` (not ServiceConfigFailureActions, WIX1149) nested in ServiceInstall for restart-on-failure.
- A component holding only `CreateFolder` needs an explicit `Guid`.
- `util:RemoveFolderEx` takes a PROPERTY with the full path set before CostInitialize (`SetProperty ... Before="CostInitialize" Sequence="execute"`), never a Directory id.
- `ServiceControl` has no Condition; to avoid starting a service that needs runtime state, omit `Start="install"` and start it from a conditional custom action (`net.exe start`, `Directory="SystemFolder"`).
- Public properties in `ExeCommand` are formatted at script-write time, so `[PAIRING_CODE]` works in deferred actions.
- Every stock WixUI set includes a licence/EULA page. With no repo licence, ship no wizard UI (use properties) rather than WiX's placeholder text.

## CI
- Pass free-text `workflow_dispatch` inputs via `env:`, not `${{ }}` inside `run:`.
- Current majors seen: checkout@v7, upload-artifact@v7, setup-dotnet@v6, rust-cache@v2.
- Test-sign the driver with a throwaway `New-SelfSignedCertificate`, verify with `Get-AuthenticodeSignature` (signtool verify /pa fails by design for self-signed), upload the .cer too.
