---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. chatgpt.com) in the browser on Linux; USB gadget spoofing, dummy_hcd, kernel rebuild, CTAP."
---

# Software security key for browser sites (no kernel work)

## Decision
- Goal "browser recognises a YubiKey" -> use Chromium's CDP **WebAuthn virtual authenticator** driven via chromedriver. Do NOT build kernel modules.
- Why not USB gadget: laptops have no UDC (`/sys/class/udc` empty), cables/Limine can't add one. `modprobe dummy_hcd` does create a virtual UDC and a gadget enumerates (1050:0407, hidraw node), but Arch kernels lack `CONFIG_USB_F_HIDG`, so nothing can answer CTAPHID. Only revisit with a custom kernel, and out-of-tree modules need rebuild every kernel update.
- Gadget route is the only one visible to system tools (ykman, sudo, SSH); PIV/CCID is not emulatable that way.

## Recipe (verified Chromium 152, chromedriver same version)
1. `chromedriver --port=P --allowed-ips=127.0.0.1`; POST `/session` with `goog:chromeOptions` binary `/usr/bin/chromium`, `--user-data-dir=<dedicated dir>` (default profile is blocked for debugging).
2. CDP via `POST /session/<sid>/goog/cdp/execute` with body `{"cmd": ..., "params": {...}}` (key is `params`, NOT `parameters`).
3. Must call `WebAuthn.enable` first, then `WebAuthn.addVirtualAuthenticator` with options: protocol ctap2, ctap2Version ctap2_1, transport usb, hasResidentKey, hasUserVerification, isUserVerified, automaticPresenceSimulation all true.
4. `WebAuthn.getCredentials` and `addCredential` require `authenticatorId`; use them to persist credentials (authenticator dies with the browser).
5. Persist sealed with `age --passphrase`; age needs a tty for passphrases, so run it under a private pty (`pty.openpty`, `setsid` + `TIOCSCTTY` in preexec_fn) and write the PIN to the master fd.
6. On exit, DELETE the WebDriver session before terminating chromedriver, then wait until no process has the profile as `--user-data-dir`; otherwise Chromium orphans and holds SingletonLock, and the next session fails "Chrome instance exited".

## Gotchas
- `age-keygen` prints the secret key to stdout and the public key to stderr; use `age-keygen -y` to derive the recipient.
- `subprocess.run` cannot take both `stdin=` and `input=`.
- Test page must be on localhost (secure context); serve with `python3 -m http.server`.
- sudo here uses fingerprint; bash tool can't prompt, so ask the user to run `sudo -v` themselves.
- Sites may reject virtual keys that require hardware attestation.
