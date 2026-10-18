---
name: bitwarden-passkey-passless-bridge-facts
description: "Use when building a Linux passkey/FIDO2 virtual authenticator (passless, UHID) backed by Bitwarden fido2Credentials, or converting passkeys between them."
---

# Bitwarden <-> passless passkey bridge: verified facts

## Bitwarden `login.fido2Credentials[]` entry (all strings)
Source: bitwarden/clients `fido2-authenticator.service.ts`, `credential-id-utils.ts`, `fido2-utils.ts`; confirmed in the `bw` binary (`Fido2CredentialExport`).
- `credentialId`: 16-byte id -> canonical UUID string; any other length -> `"b64." + base64url`.
- `keyType`="public-key", `keyAlgorithm`="ECDSA", `keyCurve`="P-256" (ES256 only; nothing else fits).
- `keyValue`: unpadded base64url of PKCS#8 DER private key. `userHandle`: unpadded base64url.
- `counter`: decimal string (parseInt). `discoverable`: literal "true"/"false". `creationDate`: ISO-8601 (new Date()).
- Bitwarden reports BE=1 BS=1 for all passkeys, so imported creds must stay "backedUp" in passless or strict RPs reject.
- One passkey per login item in Bitwarden's own flow.

## passless (pando85/passless, v0.20.2, Rust, UHID)
- Release tarball + .sha256 on GitHub; verify with sha256sum. Runs as normal user but needs /dev/uhid (default root:root 0600).
- Setup needs sudo: `uhid` in /etc/modules-load.d, `fido` group, udev `KERNEL=="uhid", GROUP="fido", MODE="0660"`, user in `fido`, relogin.
- Backends: pass (GPG, files `<rpId>/<hex credId>.gpg`), local, tpm. Env: PASSLESS_BACKEND_TYPE, PASSLESS_LOCAL_PATH, PASSLESS_PASS_STORE_PATH.
- Record is a CBOR map: id, rp{id,name}, user{id,name,display_name}, sign_count, alg(-7), private_key (raw 32-byte P-256 scalar), created, discoverable, backup_state, extensions. Byte fields may be int arrays or byte strings; Options need CBOR null (fido2.cbor cannot encode None -> hand-rolled encoder needed).
- README warns sandboxed (Flatpak/Snap) and some Electron apps may not see the hidraw device; test Discord explicitly.

## bw CLI gotchas
- `bw` commands block on a hidden master-password prompt when locked; run with `--nointeraction` or never background them.
- `bw status` takes ~2.7s; `bw serve` (default localhost:8087) exposes POST /unlock, /sync, GET /list/object/items, POST/PUT/DELETE /object/item[/:id].
- bw is a pkg binary: extract JS with `strings -n 6 /usr/bin/bw` to read class definitions.
- Desktop app.asar (npx @electron/asar extract) is minified; the CLI strings are more readable.
- Tool note: `find` tool can fail when its judge model key is expired; use grep.
