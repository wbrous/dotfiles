---
name: arch-libvirt-virtnetworkd-socket-missing
description: "Use when virt-manager, an installer (\"Validating install media failed\"), or another libvirt client fails with \"Failed to connect socket to '/var/run/libvirt/virt{network,storage,nodedev,secret}d-sock': No such file or directory\" on Arch Linux — a modular virt*d daemon/socket is inactive or disabled. Companion to arch-libvirt-virtqemud-not-running."
---

# Arch: modular libvirt daemon socket missing (virtnetworkd, virtstoraged, virtnodedevd, virtsecretd)

## Symptom

A libvirt client shows e.g.:

```
Error starting domain: Failed to connect socket to '/var/run/libvirt/virtnetworkd-sock': No such file or directory
```

or a VM installer app: `Validating install media '<iso>' failed: Failed to connect socket to '/var/run/libvirt/virtstoraged-sock': ...`

The socket (symlink to `/run/libvirt/<daemon>-sock`) does not exist. `virtqemud` may be running fine; only another driver daemon is down.

## Root cause

Modern Arch libvirt (12.x+) uses **modular daemons** (`virtqemud`, `virtnetworkd`, `virtnodedevd`, `virtsecretd`, `virtstoraged`, `virtproxyd`). Their units ship **disabled by default**. Never-enabled sockets never appear, so any client needing that driver fails. Map: network→virtnetworkd, storage pools/ISO validation→virtstoraged, host devices→virtnodedevd, secrets→virtsecretd.

## Diagnosis

```bash
systemctl list-units --all | grep -iE 'virt.*d.*\.(service|socket)'   # find inactive daemons
systemctl is-enabled virtstoraged.socket
ls -la /run/libvirt/ | grep sock
```

Legacy `libvirtd.*` being inactive is NORMAL; don't start it.

## Fix (enable sockets; services start on demand)

Enable all missing drivers at once (do all three sockets per daemon: plain, -ro, -admin):

```bash
sudo systemctl enable --now virtstoraged.socket virtstoraged-ro.socket virtstoraged-admin.socket \
  virtnodedevd.socket virtnodedevd-ro.socket virtnodedevd-admin.socket \
  virtsecretd.socket virtsecretd-ro.socket virtsecretd-admin.socket
# network daemon, if it is the one missing:
sudo systemctl enable --now virtnetworkd.socket virtnetworkd-ro.socket virtnetworkd-admin.socket
```

Verify (socket activation spawns the daemon):

```bash
virsh -c qemu:///system pool-list --all   # storage: default pool listed
virsh -c qemu:///system net-list --all    # network
```

No reboot needed; reopen the client app if it cached the failed connection.

## Notes

- `virbr0` may show DOWN with no VM running — normal.
- Use `virsh -c qemu:///system ...`; bare `virsh` may query the wrong socket and show empty lists.
- Sudo on this machine (Omarchy, wils) is fingerprint-gated: run via a PTY and let the user scan ("Place your right index finger...").
