---
name: arch-libvirt-virtnetworkd-socket-missing
description: "Use when virt-manager (or another libvirt UI) fails with \"Failed to connect socket to '/var/run/libvirt/virtnetworkd-sock': No such file or directory\" on Arch Linux, or when starting/listing a VM works via virtqemud but network management is unreachable — the modular virtnetworkd daemon/socket is inactive or disabled. Companion to arch-libvirt-virtqemud-not-running; same pattern applies to other modular virt*d daemons."
---

# Arch: virtnetworkd socket missing (modular libvirt daemon)

## Symptom

virt-manager shows an error dialog when starting/connecting:

```
Error starting domain: Failed to connect socket to '/var/run/libvirt/virtnetworkd-sock': No such file or directory
```

The socket `/var/run/libvirt/virtnetworkd-sock` (a symlink to `/run/libvirt/virtnetworkd-sock`) does not exist. `virtqemud` (QEMU daemon) may be running fine — the guest-execution daemon is up, but the **network** daemon is down, so network management is unreachable.

## Root cause

Modern Arch libvirt (12.x+) uses **modular daemons** (`virtqemud`, `virtnetworkd`, `virtnodedevd`, `virtsecretd`, `virtstoraged`, `virtproxyd`). The `virtnetworkd.service`/`virtnetworkd.socket` units ship **disabled by default** (`preset: disabled`). If they were never enabled (or got stopped), the socket file never appears and any client that needs network management fails with this error.

## Diagnosis

```bash
systemctl list-units --all | grep -iE 'virt.*d\.(service|socket)'   # spot which modular daemons are inactive
systemctl is-active virtnetworkd        # inactive
systemctl is-enabled virtnetworkd       # disabled
ls -la /run/libvirt/virtnetworkd-sock   # No such file or directory
```

Note: `virsh net-list --all` may return an empty list when queried through the wrong socket even after the fix; use `virsh -c qemu:///system net-list --all` to query through the proper driver connection.

## Fix

```bash
sudo systemctl enable --now virtnetworkd.socket
sudo systemctl enable --now virtnetworkd.service
```

(`enable --now` also wires the `-ro` and `-admin` sockets; do both commands — the socket alone can sit idle.)

Verify:

```bash
systemctl is-active virtnetworkd          # active
ls -la /run/libvirt/virtnetworkd-sock     # socket exists
virsh -c qemu:///system net-list --all    # default network visible
virsh net-info default                    # Active: yes, Bridge: virbr0
```

## Notes

- `virbr0` may show `DOWN` when no VM is running — normal; it gets carrier when a guest NIC attaches.
- The same diagnostic pattern applies to any other missing `/var/run/libvirt/virt*d-sock` (e.g. `virtnodedevd-sock`, `virtsecretd-sock`): find the inactive daemon, `systemctl enable --now <daemon>.socket` + `.service`.
- Do not start the legacy monolithic `libvirtd.service` as a workaround on modular setups — enable the specific modular daemon instead.
- On this user's machine (Omarchy/Arch, wils), sudo is fingerprint-gated: the first sudo in a PTY session triggers a polkit fingerprint prompt ("Place your right index finger on the fingerprint reader") — run commands through an interactive PTY and let the user scan.
