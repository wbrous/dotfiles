# Passkeys, WebAuthn, SSH passwords, and sudo prompts

Virtual FIDO2 authenticators on Linux, password-only SSH without sshpass, interactive sudo from headless tools, and fingerprinting a site's auth provider.

## Bitwarden ↔ passless passkey bridge (verified facts)

Bitwarden `login.fido2Credentials[]` (all strings; source: `fido2-authenticator.service.ts`, `credential-id-utils.ts`): `credentialId` = 16-byte id → canonical UUID, else `"b64." + base64url`; `keyType`="public-key", `keyAlgorithm`="ECDSA", `keyCurve`="P-256" (ES256 only); `keyValue` = unpadded base64url PKCS#8 DER; `userHandle` unpadded base64url; `counter` decimal string; `discoverable` literal "true"/"false"; Bitwarden reports BE=1 BS=1 for all passkeys, so imported creds must be BE=1 or strict RPs reject; one passkey per login item in Bitwarden's flow.

passless (pando85/passless v0.20.2, UHID; cargo package `passless-rs`, build `--features agent` ~2.5 min): local record `<store>/<rpId>/<hex credId>.bin` (CBOR map: id, rp, user, sign_count, alg(-7), raw 32-byte private scalar, created, discoverable, backup_state; needs CBOR null — `fido2.cbor` can't encode None, hand-roll); directory indexed once at startup (pull from vault BEFORE starting daemon); atomic write `.tmp.<pid>.<name>` + rename; first-credential inotify `-r` misses the event (mkdir+rename before watch attaches — watch any create/moved_to/close_write + idempotent full push after settle). Env: `PASSLESS_BACKEND_TYPE`, `PASSLESS_LOCAL_PATH`, `PASSLESS_INTERACTION_MODE=automatic`, `PASSLESS_ENABLE_CREDENTIAL_BACKUP`. Upstream bug: `build_authenticator_with_interaction` hard-codes `use_agent_options=true` so the human daemon gets agent options and `NotEligible` backup state — fix `let use_agent_options = interaction_manager.is_some();` + `Eligible` when `!is_agent && enable_credential_backup` (flags 0x45→0x4d; probe BE via resident registration authData flags & 0x08). Release binary needs this patch; AUR passless-bin lacks it. `cargo test` on debug only (`--release` fails 2 tests on `cfg!(debug_assertions)`).

`/dev/uhid` (Arch): root:root 0600; setup `uhid` in `/etc/modules-load.d/fido.conf`, `groupadd --system fido`, `usermod -aG fido $USER`, udev `KERNEL=="uhid", GROUP="fido", MODE="0660"`, `udevadm trigger --action=change /sys/devices/virtual/misc/uhid`; hidraw gets `uaccess` via 60-fido-id.rules; new group needs fresh login (systemd user units reject `SupplementaryGroups=`, `newgrp fido <<< 'cmd'` works). sudo needs fingerprint PTY (never `sudo -n`).

`bw`/`bw serve`: `bw` blocks on hidden master-password prompt when locked (`bw status` ~2.7s); serve binds `[::1]` only (use `localhost:PORT`); envelope `{"success","data","message"}` — GET /status is 200 even locked, locked routes/wrong password are HTTP 400 so parse error bodies (close HTTPError); Origin header → 403; `GET /list/object/items` → `data.data[]`; serve holds unlocked state (no BW_SESSION; prompt via `zenity --entry --hide-text`, POST /unlock once). `bw` is a pkg binary (`strings -n 6 /usr/bin/bw` readable JS). Shell gotchas: `mkdir -p -m 700 a/b` only sets `b` (`install -d -m 700`); reused PTY names replay stale logs (daemons write own log files); E2E via python-fido2 against a faithful stand-in serve (IPv6 loopback, HTTP-400 errors).

_Migrated from: bitwarden-passkey-passless-bridge-facts_

## Chromium virtual WebAuthn security key (fake YubiKey)

Drive pages' `navigator.credentials.create()/get()` via `WebAuthn.addVirtualAuthenticator` over CDP — no USB gadget (laptop USB4/xHCI is host-only, `/sys/class/udc` empty). A full implementation gates new tabs/iframes (`Target.setAutoAttach` + `waitForDebuggerOnStart`), shims `navigator.credentials` for terminal-touch gating + AAGUID patching, seals creds with `age --passphrase` (PIN via private pty), single-threaded CDP loop.

**Never edit a signed attestation after the fact:** `MakeCredential` returns `fmt: "packed"` signed by Chromium's well-known batch key covering `authenticatorData` byte-for-byte (AAGUID at offset 37). Byte-patching the AAGUID passes local byte-search/roundtrip tests but real RPs checking the signature reject it (OpenAI: `passkey_verification_failed`, HTTP 400). Prove before shipping: decode CBOR attestationObject, verify `attStmt.sig` over `authData + sha256(clientDataJSON)` with `openssl pkeyutl -verify` (hand-roll a ~40-line CBOR decoder if no library). Fix: rebuild as `fmt: "none"` (`attStmt: {}` — the standard attestation downgrade; AAGUID still readable from authData, no signature to break), patching a *copy* of authData. JS-level overrides don't affect Chromium's internal store, so later `get()` still works.

Other pitfalls: site attestation requirements are opaque until tested live (capture the real failing request/response); `navigator.credentials === undefined` on `chrome-error://chromewebdata/` = test HTTP server race, not WebAuthn; single-thread CDP only (fire without `awaitPromise`, poll `window.__done`, touch from the same thread); scope `pkill -f` to test paths/VYKEY_DIR, never bare `"chromium"`; `pip`/`sudo pacman` may be unavailable — prefer `openssl` CLI + hand-rolled decoders.

_Migrated from: chromium-virtual-webauthn-security-key_

## Fingerprinting a website's auth provider

Decide in-house vs vendor from outside with evidence: `curl` the full HTML (reader truncates; Python `urllib` gets Cloudflare-403, use `curl`), probe `/.well-known/openid-configuration`, `/jwks.json`, `/oauth-authorization-server`, Better Auth `/api/auth/get-session` + `/api/auth/ok`, `/api/config`; grep the bundle for vendor names (better-auth, supabase, clerk, auth0, workos, stytch, firebase, keycloak, zitadel, logto, kratos, hanko, lucia, authjs, next-auth, simplewebauthn, hono) and `grep -oE '"/(api|auth|oauth)[A-Za-z0-9_/.-]*'`. Bespoke `/api/login/*` + `/api/me/*` + custom error codes + no vendor strings + own OIDC discovery ⇒ in-house; `/api/auth/*`, `/realms/`, `/auth/v1/` ⇒ that product. Caveat: backend libs (JOSE, SimpleWebAuthn, Hono) are invisible externally — report observed vs inferred.

_Migrated from: fingerprint-website-auth-provider_

## Password-only SSH without sshpass

When `ssh://` fails `Permission denied (publickey,password)` and only a password exists (no sshpass, no sudo): OpenSSH 8.4+ `SSH_ASKPASS_REQUIRE=force` feeds the password without a TTY:
```sh
cat > /tmp/askpass/pw.sh <<'EOF'
#!/bin/sh
echo "THE_PASSWORD"
EOF
chmod +x /tmp/askpass/pw.sh
export SSH_ASKPASS=/tmp/askpass/pw.sh SSH_ASKPASS_REQUIRE=force

ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no \
  -o StrictHostKeyChecking=accept-new root@HOST "cmd1 && cmd2" </dev/null
```
No `setsid` (detaches stdout); `</dev/null` stops pipe-passphrase reads; repeat exports per shell call; clean up `/tmp/askpass` (plaintext password).


## Syncing a forked monorepo subfolder from upstream

When a private fork's subfolder tracks an upstream repo and needs updating without dragging in unrelated upstream changes: commit local changes first, `git remote add upstream <url>` + `git fetch upstream main`, sanity-check divergence both directions (`git log --oneline HEAD..upstream/main -- <subfolder>` and reverse — watch for re-authored copies of upstream commits under a bot identity), `git diff --stat HEAD upstream/main -- <subfolder>`, then `git checkout upstream/main -- <subfolder>` (overwrites only that path; safer than full merge when the fork has unrelated infra differences). Manually reapply real local customizations (env-var passthrough, internal IPs), `git add` + `commit`, smoke-verify (`python3 -m py_compile`, `docker compose config -q`). Don't rebuild/restart live containers unasked — flag as follow-up.

_Migrated from: ssh-password-auth-without-sshpass_

## Interactive sudo from headless tools (fingerprint auth)

`sudo -n` means "never prompt at all" — fingerprint scans count as prompts, so it fails with `a password is required` in TTY-less tools. `sudo -v` refreshes cached creds (5-min window) and CAN trigger the fingerprint prompt. Fix: launch via hub `start` (real PTY, `pty` defaults true), `wait` for exit, `logs` for output ("Place your right index finger..."). `script -qec "sudo -n true" /dev/null` still fails (PTY doesn't override `-n`); `script -qec "sudo -v" /dev/null` works. After caching, `sudo -n` succeeds within the window.

_Migrated from: sudo-interactive-tty-via-hub_
