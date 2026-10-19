#!/bin/bash
# One-time root setup so a normal user can create a virtual FIDO2 key via /dev/uhid.
# Usage: sudo uhid-setup.sh <username>
set -euo pipefail

user="${1:?usage: uhid-setup.sh <username>}"
[[ $EUID -eq 0 ]] || { echo "must run as root" >&2; exit 1; }
id -u "$user" >/dev/null

echo uhid >/etc/modules-load.d/fido.conf
modprobe uhid

# sysusers.d is how passless itself ships the group; groupadd is the fallback.
getent group fido >/dev/null || groupadd --system fido
usermod -aG fido "$user"

echo 'KERNEL=="uhid", GROUP="fido", MODE="0660"' >/etc/udev/rules.d/90-passless.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=misc --sysname-match=uhid

ls -l /dev/uhid
id "$user"
