---
name: bitwarden-passkey-passless-bridge-facts
description: "Use when building a Linux passkey/FIDO2 virtual authenticator (passless, UHID) backed by Bitwarden fido2Credentials, converting passkeys between them, or debugging passless BE/backup flag or /dev/uhid access."
---

# Bitwarden <-> passless passkey bridge: verified facts

## Bitwarden `login.fido2Credentials[]` entry (all strings)
Source: bitwarden/clients `fido2-authenticator.service.ts`, `credential-id-utils.ts`, `fido2-utils.ts`; confirmed in the `bw` binary (`Fido2CredentialExport`: counter=parseInt, discoverable==="true", creationDate=new Date()).
- `credentialId`: 16-byte id -> canonical UUID string; any other length -> `"b64." + base64url`.
- `keyType`="public-key", `keyAlgorithm`="ECDSA", `keyCurve`="P-256" (ES256 only; nothing else fits).
- `keyValue`: unpadded base64url of PKCS#8 DER private key. `userHandle`: unpadded base64url.
- `counter`: decimal string. `discoverable`: literal "true"/"false". `creationDate`: ISO-8601.
- Bitwarden reports BE=1 BS=1 for all passkeys, so imported creds must stay "backedUp" in passless or strict RPs reject.
- One passkey per login item in Bitwarden's own flow.

## passless (pando85/passless, v0.20.2, Rust, UHID)
- Release tarball + .sha256 on GitHub; verify with sha256sum. Runs as a normal user.
- Record (local backend: `<store>/<rpId>/<hex credId>.bin`; pass backend: `.gpg`) is a CBOR map: id, rp{id,name}, user{id,name,display_name}, sign_count, alg(-7), private_key (raw 32-byte P-256 scalar), key_provider(null), created, discoverable, backup_state, extensions. Byte fields are int arrays when passless writes them. Options need CBOR null; `fido2.cbor` cannot encode None, so use a hand-rolled encoder.
- Env: PASSLESS_BACKEND_TYPE, PASSLESS_LOCAL_PATH, PASSLESS_INTERACTION_MODE=automatic (skips desktop UP/UV prompt, for tests). Config file: ~/.config/passless/config.toml (`-c` / PASSLESS_CONFIG). `passless config print` ignores -c and flags; it is NOT a probe of the running daemon.
- **UPSTREAM BUG (0.20.2, agent-feature build = the release binary):** `authenticator.rs` `build_authenticator_with_interaction_and_options` hard-codes `.default_credential_backup_state(NotEligible)`, so `enable_credential_backup` (flag/env/toml) never sets BE=1 on the wire or in the stored record. Non-agent builder honours it. Fix = honour setting when `!is_agent`. Probe: register a resident credential and read authData flags (BE = 0x08).

## /dev/uhid and hidraw access (Arch/Omarchy, systemd)
- /dev/uhid is root:root 0600. One-time root setup: `uhid` in /etc/modules-load.d/fido.conf, `groupadd --system fido`, `usermod -aG fido $USER`, udev rule `KERNEL=="uhid", GROUP="fido", MODE="0660"`. Existing node needs `udevadm trigger --action=change /sys/devices/virtual/misc/uhid` (a --sysname-match trigger silently did nothing).
- The virtual key's hidraw node is tagged `uaccess` by systemd's 60-fido-id.rules (ID_FIDO_TOKEN=1), so logind ACLs it to the active seat user: browsers/Electron can open it with NO extra rule and no libfido2.
- New group does not apply to existing shells. `sg` is absent; `setpriv` cannot add groups unprivileged; `newgrp fido <<< 'cmd'` works.
- sudo here uses fingerprint: run `sudo ...` with bash `pty: true` so the prompt surfaces; `sudo -n` always fails.

## Test harness
- python-fido2 over hidraw: find CtapHidDevice named "Virtual FIDO2 Authenticator", Fido2Client + Fido2Server register/authenticate; proves end-to-end CTAP2 incl. discoverable assertion.
- Supervised (named, pty) bash services replay stale log output when a name/launcher is reused; have the daemon write its own log file and read that instead.
- Instance lock lives in /run/user/$UID/passless/*.lock; pkill + remove it before restarting.

## bw CLI gotchas
- `bw` commands block on a hidden master-password prompt when locked; use `--nointeraction` or never background them.
- `bw status` ~2.7s; `bw serve` (localhost:8087) exposes POST /unlock, /lock, /sync, GET /status, GET /list/object/items, GET|POST|PUT|DELETE /object/item[/:id].
- bw is a pkg binary: `strings -n 6 /usr/bin/bw` shows readable JS class definitions.
- `find` tool can fail when its judge key is expired; use grep.
