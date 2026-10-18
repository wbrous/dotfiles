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
- Bitwarden reports BE=1 BS=1 for all passkeys, so imported creds must be BE=1 in passless or strict RPs reject.
- One passkey per login item in Bitwarden's own flow.

## passless (pando85/passless, v0.20.2, Rust, UHID) — cargo package is `passless-rs`
- Release tarball + .sha256 on GitHub; verify with sha256sum. Runs as a normal user.
- Record (local backend: `<store>/<rpId>/<hex credId>.bin`; pass backend: `.gpg`) is a CBOR map: id, rp{id,name}, user{id,name,display_name}, sign_count, alg(-7), private_key (raw 32-byte P-256 scalar), key_provider(null), created, discoverable, backup_state, extensions. Byte fields are int arrays when passless writes them. Options need CBOR null; `fido2.cbor` cannot encode None, so use a hand-rolled encoder.
- The local backend indexes its directory ONCE at startup and never rescans: files written while it runs are invisible until restart. So pull from the vault BEFORE starting the daemon.
- Env: PASSLESS_BACKEND_TYPE, PASSLESS_LOCAL_PATH, PASSLESS_INTERACTION_MODE=automatic (skips desktop UP/UV prompt, for tests), PASSLESS_ENABLE_CREDENTIAL_BACKUP. Config file: ~/.config/passless/config.toml (`-c` / PASSLESS_CONFIG). `passless config print` ignores -c and flags; it is NOT a probe of the running daemon.
- **UPSTREAM BUG (0.20.2, agent-feature build = the release binary):** in `cmd/passless/src/authenticator.rs`, `build_authenticator_with_interaction` (used by the human daemon via `with_pin_storage`) hard-codes `use_agent_options = true`, so the human authenticator gets AGENT options AND a hard-coded `default_credential_backup_state(NotEligible)`; `enable_credential_backup` (flag/env/toml) can never give BE=1. Fix: `let use_agent_options = interaction_manager.is_some();` (same rule as the key-provider builder), and in the agent builder set backup state `Eligible` when `!is_agent && enable_credential_backup`. Verified: authData flags 0x45 -> 0x4d (BE=1) and stored backup_state notEligible -> eligible. A first attempt that only guarded the backup line with `!is_agent` did nothing because is_agent was always true.
- Probe for BE: register a resident credential, read `auth_data.flags` (BE = 0x08). GetInfo options are not a reliable probe for makeCredUvNotRqd.
- cargo test notes: use the debug profile. `--release` fails 2 tests in agent::storage_factory (test_shared_delegated_*) because cfg!(debug_assertions) disables the no-prompt local-storage constructor; they pass in debug. Test filter `authenticator` matches 0 tests; names are `authenticator::tests::*`. Build ~2.5 min.

## /dev/uhid and hidraw access (Arch/Omarchy, systemd)
- /dev/uhid is root:root 0600. One-time root setup: `uhid` in /etc/modules-load.d/fido.conf, `groupadd --system fido`, `usermod -aG fido $USER`, udev rule `KERNEL=="uhid", GROUP="fido", MODE="0660"`. Existing node needs `udevadm trigger --action=change /sys/devices/virtual/misc/uhid` (a --sysname-match trigger silently did nothing).
- The virtual key's hidraw node is tagged `uaccess` by systemd's 60-fido-id.rules (ID_FIDO_TOKEN=1), so logind ACLs it to the active seat user: browsers/Electron can open it with NO extra rule and no libfido2.
- New group does not apply to existing shells. `sg` is absent; `setpriv` cannot add groups unprivileged; `newgrp fido <<< 'cmd'` works.
- sudo here uses fingerprint: run `sudo ...` with bash `pty: true` so the prompt surfaces; `sudo -n` always fails.
- /run/user/$UID is tmpfs: a good home for decrypted working credentials (RAM only).

## Test harness
- python-fido2 over hidraw: find CtapHidDevice named "Virtual FIDO2 Authenticator", Fido2Client + Fido2Server register/authenticate; proves end-to-end CTAP2 incl. discoverable assertion.
- Supervised (named, pty) bash services replay stale log output when a name/launcher is reused; have the daemon write its own log file and read that instead.
- Instance lock lives in /run/user/$UID/passless/*.lock; pkill + remove it before restarting.

## bw CLI / bw serve
- `bw` commands block on a hidden master-password prompt when locked; use `--nointeraction` or never background them. `bw status` ~2.7s.
- `bw serve` binds IPv6 loopback ONLY here ([::1]:8087): use `http://localhost:8087`, not 127.0.0.1. Run it as a managed service; `( ... &)` gets reaped.
- Envelope: {"success":bool,"data":...,"message":...}. GET /status -> data.template.status ("locked"/"unlocked", success even when locked). Locked data routes -> success:false, "Vault is locked."; wrong password -> "Cryptography error, The decryption operation failed". GET /list/object/items -> data.data[]. Requests with an Origin header get 403 (CSRF protection; never pass --disable-origin-protection).
- bw serve keeps the unlocked state in its own memory: there is NO BW_SESSION to store. `bw unlock` invalidates earlier session keys. Do not store the master password in the keyring (anyone in the session could then open the whole vault); prompt with `zenity --entry --hide-text` and POST /unlock once.
- omarchy conventions: bin scripts have `# omarchy:summary=`/`# omarchy:args=` headers, secrets via stdout/stdin never argv. omarchy-menu-input has no masked mode.
- bw is a pkg binary: `strings -n 6 /usr/bin/bw` shows readable JS class definitions. `find` tool can fail when its judge key is expired; use grep.
