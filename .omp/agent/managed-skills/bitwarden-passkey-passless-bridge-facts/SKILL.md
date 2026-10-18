---
name: bitwarden-passkey-passless-bridge-facts
description: "Use when building a Linux passkey/FIDO2 virtual authenticator (passless, UHID) backed by Bitwarden fido2Credentials, converting passkeys between them, syncing via bw serve, or debugging passless BE/backup flag, /dev/uhid access, or inotify/systemd-user-unit issues for it."
---

# Bitwarden <-> passless passkey bridge: verified facts

## Bitwarden `login.fido2Credentials[]` entry (all strings)
Source: bitwarden/clients `fido2-authenticator.service.ts`, `credential-id-utils.ts`, `fido2-utils.ts`; confirmed in the `bw` binary (`Fido2CredentialExport`).
- `credentialId`: 16-byte id -> canonical UUID string; any other length -> `"b64." + base64url`.
- `keyType`="public-key", `keyAlgorithm`="ECDSA", `keyCurve`="P-256" (ES256 only).
- `keyValue`: unpadded base64url of PKCS#8 DER private key. `userHandle`: unpadded base64url.
- `counter`: decimal string. `discoverable`: literal "true"/"false". `creationDate`: ISO-8601.
- Bitwarden reports BE=1 BS=1 for all passkeys, so imported creds must be BE=1 in passless or strict RPs reject.
- One passkey per login item in Bitwarden's own flow.

## passless (pando85/passless v0.20.2, UHID) — cargo package is `passless-rs`, build with `--features agent` (~2.5 min)
- Release tarball + .sha256 on GitHub; verify with sha256sum. Runs as normal user.
- Local backend record: `<store>/<rpId>/<hex credId>.bin`, CBOR map: id, rp{id,name}, user{id,name,display_name}, sign_count, alg(-7), private_key (raw 32-byte scalar), key_provider(null), created, discoverable, backup_state, extensions. Needs CBOR null; `fido2.cbor` cannot encode None -> hand-rolled encoder.
- Local backend indexes the directory ONCE at startup: pull from vault BEFORE starting the daemon.
- Atomic write = `.tmp.<pid>.<name>` then rename. For the FIRST credential on a new site, inotify `-r` misses the file event (passless mkdirs the site dir and renames before the watch attaches; only CREATE,ISDIR arrives). Watchers must trigger on any create/moved_to/close_write and run an idempotent full push after a settle delay.
- Env: PASSLESS_BACKEND_TYPE, PASSLESS_LOCAL_PATH, PASSLESS_INTERACTION_MODE=automatic (tests), PASSLESS_ENABLE_CREDENTIAL_BACKUP. `passless config print` ignores flags: not a probe of the running daemon.
- **UPSTREAM BUG:** `build_authenticator_with_interaction` hard-codes `use_agent_options=true`, so the human daemon gets agent options and `NotEligible` backup state; `enable_credential_backup` can never give BE=1. Fix: `let use_agent_options = interaction_manager.is_some();` and in the agent builder `Eligible` when `!is_agent && enable_credential_backup`. Verified authData flags 0x45 -> 0x4d; advertised GetInfo options are identical before/after. Probe BE by registering a resident credential and reading authData flags & 0x08. Release binary needs this patch; AUR passless-bin does not have it.
- cargo test: use debug profile; `--release` fails 2 tests (test_shared_delegated_*) because cfg!(debug_assertions) gates no-prompt storage creation.

## /dev/uhid and hidraw (Arch/Omarchy, systemd)
- /dev/uhid root:root 0600. Root setup: `uhid` in /etc/modules-load.d/fido.conf, `groupadd --system fido`, `usermod -aG fido $USER`, udev `KERNEL=="uhid", GROUP="fido", MODE="0660"`; apply to existing node with `udevadm trigger --action=change /sys/devices/virtual/misc/uhid`.
- Virtual key's hidraw is tagged `uaccess` (60-fido-id.rules) -> logind ACL gives the seat user access with no extra rule.
- New group not in existing shells/user manager. `sg` absent, `setpriv` can't add groups; `newgrp fido <<< 'cmd'` works (use a wrapper script, avoid nested quotes).
- systemd USER units cannot use `SupplementaryGroups=` (fails 216/GROUP); the user manager needs the group from a fresh login. PrivateTmp/ProtectSystem/NoNewPrivileges/ReadWritePaths=%t/... work in user units.
- sudo uses fingerprint: run with bash `pty: true`; `sudo -n` always fails.

## bw CLI / bw serve
- `bw` blocks on a hidden master-password prompt when locked; never background it unguarded. `bw status` ~2.7s.
- `bw serve` binds [::1] only: use `http://localhost:PORT`, not 127.0.0.1. Run as a managed service (`( ... &)` gets reaped).
- Envelope {"success":bool,"data":...,"message":...}. GET /status is HTTP 200 even when locked (data.template.status). Locked data routes AND wrong password return HTTP **400** with the envelope in the body: a client must parse the body of HTTP errors (and close the HTTPError, ResourceWarning otherwise). Origin header -> 403. GET /list/object/items -> data.data[]. Never use --disable-origin-protection.
- bw serve holds unlocked state itself: no BW_SESSION to store; don't keep the master password in the keyring; prompt via `zenity --entry --hide-text` and POST /unlock once.
- omarchy conventions: bin scripts with `# omarchy:summary=` headers; secrets never in argv; user units in default/systemd/user and enabled by install/user/first-run/enable-user-units.sh; opt-in installers named `omarchy-install-service-*` / `omarchy-remove-service-*`.
- bw is a pkg binary: `strings -n 6 /usr/bin/bw` shows readable JS. `find` tool can fail when its judge key expires; use grep.

## Shell/test gotchas hit
- `mkdir -p -m 700 a/b` only sets b; parents get 755. Use `install -d -m 700 a a/b`. A watcher must not create/chmod parents it doesn't own (once tried to chmod /tmp).
- Supervised named pty services replay stale logs when a name is reused; have daemons write their own log file. Instance lock: /run/user/$UID/passless/*.lock, remove after kill.
- E2E recipe (all passed): register via python-fido2 (CtapHidDevice "Virtual FIDO2 Authenticator"), push, wipe local store, pull BEFORE daemon start, assert (discoverable, no allowList) verified against the original public key, counter push. Use a faithful stand-in bw serve (IPv6 loopback, HTTP 400 errors) rather than the real vault.
