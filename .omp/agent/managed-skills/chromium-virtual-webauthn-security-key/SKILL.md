---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. ChatGPT, Apple): use Chromium's CDP virtual authenticator, not USB gadget/kernel work; covers PIN-sealed persistence, Enter plug/unplug toggle for phone-QR fallback, and bot-detection stealth."
---

# Software security key for a browser (Chromium CDP virtual authenticator)

## Decision: do NOT go down the USB/kernel path
- Laptops have no USB device controller (UDC); `/sys/class/udc` is empty. Cables, Limine edits and sudo don't change that.
- `modprobe dummy_hcd` does give a virtual UDC and a gadget can enumerate as 1050:0407, but the stock Arch/omarchy kernels lack `f_hidg` (no userspace HID), so nothing can answer CTAPHID. A custom kernel plus a full CTAP2 responder would be needed. Not worth it.
- No software PIV/CCID emulation exists that ykman/sudo/SSH accept. Browser WebAuthn is the realistic target.
- Real answer: Chromium's DevTools `WebAuthn.*` virtual authenticator. Sites cannot tell it from a USB key.

## CDP gotchas (verified on Chromium 152)
- Call `WebAuthn.enable` BEFORE `addVirtualAuthenticator`, else "Virtual Authenticator Environment has not been enabled".
- chromedriver endpoint `/goog/cdp/execute` takes `{"cmd":..., "params":...}` (NOT `parameters`).
- `getCredentials`/`addCredential` need `authenticatorId`. Options used: ctap2, ctap2_1, usb, hasResidentKey, hasUserVerification, isUserVerified, automaticPresenceSimulation=true.
- WebAuthn needs a secure origin: use `http://localhost:PORT`, not `data:`.
- Authenticator lives only in browser memory: persist `getCredentials` output, re-inject with `addCredential` next launch. Sign counts must be written back on exit.
- Presence cannot be flipped on an already-waiting request; toggling `setAutomaticPresenceSimulation` mid-request does nothing.

## Persistence with a PIN
- Seal credentials with `age --passphrase`. age only reads passphrases from a tty, so run it under a private pty (`pty.openpty`, `setsid` + `TIOCSCTTY` in preexec) and type the PIN into the master fd. Piping stdin does not work.
- Atomic write (tmp + fsync + replace), mode 0600, dir 0700.

## Phone-QR fallback: Enter toggles plugged/unplugged
- Unplug = `WebAuthn.removeVirtualAuthenticator` AND `WebAuthn.disable`. Removing the authenticator alone leaves the request hanging with no dialog; disabling the environment too makes Chromium show its normal "Passkeys & Security Keys" dialog with the QR code (screenshot-verified).
- Save `getCredentials` before removing; re-plug = `enable` + add authenticator + `addCredential` each.
- A request left on the QR dialog stays stuck and later requests fail with OperationError; only `Page.reload` clears it. Track in-flight calls with an observe-only `Page.addScriptToEvaluateOnNewDocument` counter wrapping `navigator.credentials.create/get`; reload only when count > 0 on re-plug.
- Virtual mode disables real transports, so QR phone completion needs the key unplugged; can't have both live at once.
- Gating requests by wrapping `credentials.get` in a page promise was tried and abandoned (superseded by the toggle).

## Stealth (sites like auth.openai.com sit behind Cloudflare "Verify you are human")
- chromedriver injects `cdc_*` globals into pages: a known bot tell. Drive Chromium directly with `--remote-debugging-pipe` instead (fds 3 read / 4 write, NUL-terminated JSON, `Target.getTargets` then `Target.attachToTarget flatten:true`, send commands with `sessionId`). Same CDP, WebAuthn works, no cdc globals.
- With a debugging pipe `navigator.webdriver` is true unless `--disable-blink-features=AutomationControlled` is passed. Verified false with it.
- Close with `Browser.close`, then wait for the process; a leaked Chromium keeps the profile SingletonLock and the next launch dies ("Chrome instance exited").
- Do not spoof UA/WebGL/canvas: inconsistency raises detection. Clear a poisoned profile dir (`rm -rf ~/.config/vykey/chromium-profile`) if Cloudflare remembered a challenge.
- NOT verified: whether the pipe build actually passes ChatGPT's Cloudflare challenge. Could not get a meaningful result from the unauthenticated authorize URL.

## Testing tips
- Test with a real WebAuthn ceremony against a localhost page with register/login buttons; check same credential id signs in after restart and sign count increments.
- Background `python3 -m http.server` dies with the launching shell; run it as a named managed service.
- `sudo` here uses fingerprint auth; `sudo -n` fails. Ask the user to run privileged steps themselves.
- Python deps are minimal: no `websocket`/`websockets`; chromedriver HTTP or the raw pipe avoid needing them.

## Deliverable shape
`~/.local/bin/vykey` with `init` (choose PIN), `launch [url]` (PIN prompt, own profile at `~/.config/vykey/chromium-profile`, Enter toggles plug), `status`. Works only in its own Chromium window, not the user's normal profile, and is invisible to ykman/sudo/SSH.
