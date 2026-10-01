---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. ChatGPT, passkeys.io, Apple) on Linux; Chromium CDP virtual authenticator with PIN-sealed store and Enter-to-touch; not USB gadget/PIV."
---

# Software security key for Chromium (no hardware, no kernel work)

## Decision (verified on Framework laptop, Arch, Chromium 152)
- Do NOT go down the USB-gadget route. Laptop xHCI ports are host-only (no UDC; `/sys/class/udc` empty), cables/Limine can't change that. `dummy_hcd` gives a fake UDC and enumerates as 1050:0407, but the kernels lack `CONFIG_USB_F_HIDG` (no userspace HID), so nothing answers CTAPHID. Needs custom kernel + a full CTAP2 responder. Not worth it.
- PIV/ykman/sudo/SSH cannot be satisfied by software this way. Only websites (WebAuthn) in Chromium.
- Use Chromium's CDP **virtual authenticator** driven via chromedriver (versions must match; `chromedriver` ships on Omarchy).

## CDP gotchas (chromedriver `POST /session/<id>/goog/cdp/execute`)
- Body key is `params`, NOT `parameters` ("params not passed").
- Call `WebAuthn.enable` BEFORE `addVirtualAuthenticator` ("environment not enabled").
- `getCredentials`/`addCredential` need `authenticatorId`.
- WebAuthn needs a secure origin: use `http://localhost:PORT` (data: URLs give TypeError). A page server started with `&` in a bash call dies; run it as a managed service.
- Authenticator lives only in browser memory: persist `getCredentials` output and re-inject with `addCredential` next launch (sign counts increment, verified 1->2).
- Chromium refuses CDP on the default profile; use a dedicated `--user-data-dir`.
- Session teardown: `DELETE /session/<id>` first, then kill chromedriver, then wait until no process has `--user-data-dir=PROFILE` (else orphan holds SingletonLock and next start says "Chrome instance exited").
- `excludeSwitches: ["enable-automation"]` plus `--disable-blink-features=AutomationControlled` to look less automated.

## PIN-sealed store
- `age --passphrase` refuses non-tty passphrases. Run age in a child with a private pty as controlling terminal (`os.setsid` + `TIOCSCTTY` in preexec) and write the PIN to the pty master when it prompts. Wrong PIN => nonzero exit.
- `age-keygen` prints secret key on stdout, public on stderr; stdout starts with a `# created:` comment (don't `startswith` check the whole blob).
- `subprocess.run` cannot take both `stdin=` and `input=`.

## Enter-to-touch (on-demand presence)
- Chromium decides presence when a request STARTS; enabling `setAutomaticPresenceSimulation` mid-wait does not rescue a pending request (verified: NotAllowedError after timeout).
- So: create the authenticator with `automaticPresenceSimulation: false`, inject via `Page.addScriptToEvaluateOnNewDocument` a wrapper around `navigator.credentials.create/get` (publicKey only) that holds the call behind a promise and exposes `window.__vykeyPending` / `window.__vykeyGo()`. On Enter: presence on -> `__vykeyGo()` -> wait pending cleared -> short sleep -> presence off.
- Poll `__vykeyPending` and print "<site> wants to register/sign in; press Enter". Enter with nothing pending does nothing.

## Limits to tell the user
- Works only in the Chromium window launched by the tool (own profile), invisible to system/ykman.
- Phone QR (hybrid/caBLE, e.g. Apple "sign in with iPhone") does not complete with the virtual authenticator attached: Bluetooth/real transports are disabled. Offer a `--phone` mode (same profile, no virtual key) instead. Not yet built as of last session.
- Back up the sealed credentials file; sites may reject non-hardware attestation.
- Testing a normal Chromium window shows the "insert security key" dialog; that is NOT the tool's window.

## Reference implementation
`~/.local/bin/vykey` (init / launch [url] / status), state in `~/.config/vykey`, source was /tmp/swytoken/vykey.py (~450 lines).
- Sudo here is fingerprint-based; `sudo -n` fails, ask the user to run sudo steps themselves.
