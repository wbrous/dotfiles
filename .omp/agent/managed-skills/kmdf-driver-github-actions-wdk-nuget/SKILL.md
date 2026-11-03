---
name: kmdf-driver-github-actions-wdk-nuget
description: "Building a KMDF/kernel driver (vcxproj) on a GitHub Actions Windows runner fails: ntddk.h not found, or MSB4062 ValidateNTTargetVersion / Microsoft.DriverKit.Build.Tasks.18.0.dll could not be loaded."
---

# Kernel driver build on GitHub Actions (WDK via NuGet)

## Symptoms and causes (each seen in real CI logs)

1. `error C1083: Cannot open include file: 'ntddk.h'`
   The runner image has the Visual Studio WDK *extension* (WindowsKernelModeDriver toolset) but NOT the WDK headers/libs.
   Fix: restore the WDK from NuGet, the way microsoft/Windows-driver-samples does:
   - `packages.config` with `Microsoft.Windows.SDK.CPP`, `Microsoft.Windows.SDK.CPP.x64`, `Microsoft.Windows.WDK.x64` (all the SAME version)
   - `nuget restore packages.config -PackagesDirectory packages` (download nuget.exe from dist.nuget.org if absent)
   - a `Directory.Build.props` next to the vcxproj that imports, when `Exists()` and `$(Platform)=='x64'`:
     `packages\Microsoft.Windows.WDK.x64.<v>\build\native\Microsoft.Windows.WDK.x64.props`,
     `packages\Microsoft.Windows.SDK.CPP.x64.<v>\build\native\Microsoft.Windows.SDK.cpp.x64.props`,
     `packages\Microsoft.Windows.SDK.CPP.<v>\build\native\Microsoft.Windows.SDK.cpp.props`
   - Do NOT use `dotnet restore`/`dotnet build` for this (Microsoft says it does not work with the WDK); use nuget.exe + msbuild.

2. `MSB4062: The "ValidateNTTargetVersion" task could not be loaded ... Microsoft.DriverKit.Build.Tasks.18.0.dll`
   MSBuild version must match the driver build-task DLL shipped in the WDK package:
   - `windows-latest` / `windows-2025-vs2026` = Visual Studio 2026 = MSBuild 18.0, wants `...Tasks.18.0.dll`
   - WDK NuGet `10.0.26100.x` ships only `...Tasks.17.0.dll`  -> fails on that image
   - WDK NuGet `10.0.28000.x` (e.g. 28000.1839, 28000.2526) ships `...Tasks.18.0.dll`
   So: pin the WDK/SDK packages to 10.0.28000.x AND pin `runs-on: windows-2025-vs2026` so `windows-latest` cannot drift.
   Check a candidate with: `unzip -l <pkg>.nupkg | grep Build.Tasks` (nupkg from
   https://api.nuget.org/v3-flatcontainer/microsoft.windows.wdk.x64/<v>/microsoft.windows.wdk.x64.<v>.nupkg).

3. Link error risk: `SDDL_DEVOBJ_SYS_ALL_ADM_ALL` is only declared in wdmsec.h; add `wdmsec.lib` to `Link/AdditionalDependencies`.

## Status caveat

Fix #2 (28000.2526 + windows-2025-vs2026) was chosen from the evidence above but was NOT yet confirmed by a green run when this was written. If it still fails, read the next error from `gh run view <id> --log-failed` rather than assuming this list is complete.

## Not worth trying

Syntax-checking the driver on Linux with clang-cl against the extracted NuGet headers: header-name casing and DriverSpecs.h resolution made it a rabbit hole. CI is the only reliable compiler.

## Related

Nothing here replaces signing: the driver still needs test-signing (`bcdedit /set testsigning on`) or attestation signing to load.
