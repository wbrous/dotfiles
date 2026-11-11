# Wine

Running Windows apps on Linux via Wine / GE-Proton, plus native Linux app installs that share the same launcher/icon tooling.

- [electron-apps.md](electron-apps.md) - standalone Electron .exe under Wine: launch scripts, mojo IPC vs GE-Proton choice, UISettings crash, blank text, clipped windows, desktop entries
- [webview2-tauri.md](webview2-tauri.md) - WebView2/Edge and Tauri apps: ole32 WinRT crash via GE-Proton, input.dll stubs, registry-hive gap, anti-VM stop rule
- [debugging-tracing.md](debugging-tracing.md) - relay tracing, volatile HKLM\HARDWARE, gdb/ptrace limits, Ghidra memory-dump analysis, .pak parsing, WSC shims
- [prefix-and-msi.md](prefix-and-msi.md) - project-local prefixes, silent MSI installs, stub-DLL shims (powrprof)
- [linux-app-install.md](linux-app-install.md) - native installs: vendor bundles, single binaries, icon-cache spaces fix, full Orca uninstall
