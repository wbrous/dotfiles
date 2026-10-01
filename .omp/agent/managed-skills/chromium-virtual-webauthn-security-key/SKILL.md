---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. ChatGPT, Apple, passkeys.io) in Chromium; no hardware key, USB gadget route fails."
---

# Software security key for Chromium (no hardware, no kernel work)

## Decision: do NOT do a USB gadget / kernel build
- Laptops have no UDC; `/sys/class/udc` is empty, a cable or Limine edit cannot add one.
- `dummy_hcd` does give a UDC and a gadget enumerates as 1050:0407, but the kernel lacks `f_hidg` (no `/dev/hidgX`), so nothing can answer CTAPHID. A custom kernel plus CTAP2 responder is huge and must be rebuilt per kernel.
- PIV/ykman/sudo/SSH cannot be spoofed this way. Browser WebAuthn can: use Chromium's CDP virtual authenticator.

## Mechanism
chromedriver (version must match chromium) + plain HTTP, no websocket lib needed:
- Start `chromedriver --port=P --allowed-ips=127.0.0.1`, POST `/session` with `goog:chromeOptions` (binary `/usr/bin/chromium`, `excludeSwitches:["enable-automation"]`, own `--user-data-dir`; default profile is blocked).
- CDP via `POST /session/<id>/goog/cdp/execute` with body `{"cmd": ..., "params": {...}}` (key is `params`, NOT `parameters`).
- Order: `WebAuthn.enable` first, then `addVirtualAuthenticator` (ctap2, ctap2_1, usb, hasResidentKey, hasUserVerification, isUserVerified, automaticPresenceSimulation true). `getCredentials`/`addCredential` need `authenticatorId`.
- Virtual authenticator lives only in browser memory: persist `getCredentials` output, re-inject with `addCredential` next launch (sign counts continue). Seal the store with `age --passphrase`; age reads passphrase only from a tty, so drive it through a private pty (`pty.openpty`, `setsid` + `TIOCSCTTY` in preexec_fn, write the PIN to the master when it prompts).
- Close the browser by `DELETE /session/<id>` before killing chromedriver, then wait until no process has the profile as user-data-dir, else the next launch fails on SingletonLock.
- WebAuthn needs a secure origin (localhost or https), not `data:` URLs.

## Phone QR vs virtual key (the user's real need)
- With an authenticator attached, Chromium never shows the QR/hybrid dialog and the "sign in with iPhone" flow does not complete.
- Unplug = `removeVirtualAuthenticator` AND `WebAuthn.disable`. Removing alone leaves a request hanging with no dialog; adding `disable` makes the normal "Passkeys & Security Keys" dialog with QR appear (verified by screenshot with `grim`).
- Plug = `enable` + `addVirtualAuthenticator` + `addCredential` for each saved credential.
- A request left pending on the QR dialog poisons the page: every later request fails with OperationError, even after re-plug. Only `Page.reload` clears it. Detect with an observe-only script (`Page.addScriptToEvaluateOnNewDocument` counting unsettled `navigator.credentials.create/get` promises) and reload only when something is in flight.
- `setAutomaticPresenceSimulation` cannot be toggled on a pending request (presence is decided at request start); a "press Enter to touch" design needs a JS gate wrapper and is clumsier than plug/unplug. User chose the Enter plug/unplug toggle.

## Final tool shape
`vykey init` (choose PIN), `vykey launch [url]` (type PIN; starts plugged in; Enter toggles plug/unplug; Ctrl-C or closing the window saves credentials back, sealed). Installed to `~/.local/bin/vykey`.

## Testing recipe
Run the real CLI under `pty.fork`, find the chromedriver session via `GET /sessions`, drive page buttons with `/execute/sync`. Serve the test page from a managed background service (a `&` server dies with its shell). Take screenshots to check dialogs.

## Caveats to tell the user
Only the Chromium window launched by vykey has the key, not the system (no ykman/sudo). Back up the sealed credentials file; sites may reject virtual authenticators that demand hardware attestation. Sudo here uses fingerprint: `sudo` needs the user to touch the reader; if it times out, ask the user to run it.
