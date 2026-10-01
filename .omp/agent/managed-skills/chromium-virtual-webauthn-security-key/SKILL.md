---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. ChatGPT, Apple sign-in, passkeys.io) on a laptop with no hardware key; Chromium virtual authenticator, PIN-sealed credentials, stealth, phone-QR fallback."
---

# Software security key for Chromium (what works, what does not)

## Decide first
- A real fake USB YubiKey is NOT feasible on a laptop. No UDC exists (`/sys/class/udc` empty), laptop USB-C is host-only, a cable between two host ports does nothing, and Limine/bootloader config cannot change that. `dummy_hcd` gives a UDC and a gadget enumerates as 1050:0407, but Arch kernels here have no `usb_f_hidg`, so no userspace can answer CTAPHID. Do not go down the kernel-build route. PIV/ykman/sudo/SSH cannot be emulated this way.
- For websites in a browser, use Chromium's CDP WebAuthn virtual authenticator. No kernel work.

## Architecture that worked (`vykey`, installed at ~/.local/bin/vykey)
- Launch `/usr/bin/chromium` with `--remote-debugging-pipe` (fds 3 read / 4 write, NUL-delimited JSON), NOT chromedriver. chromedriver injects `cdc_*` globals and gets bot-flagged by Cloudflare. Also pass `--disable-blink-features=AutomationControlled` (the pipe sets navigator.webdriver=true otherwise). Use a dedicated `--user-data-dir`; the default profile cannot be driven. Don't spoof UA/GPU/canvas.
- Via CDP: `Target.getTargets` -> `Target.attachToTarget{flatten:true}` -> `WebAuthn.enable` -> `WebAuthn.addVirtualAuthenticator` (ctap2, ctap2_1, usb, hasResidentKey, hasUserVerification, isUserVerified) -> `WebAuthn.addCredential`. getCredentials/removeVirtualAuthenticator need `authenticatorId`. Chromedriver's `/goog/cdp/execute` uses key `params`, not `parameters`.
- Credentials live only in browser memory, so persist them: `WebAuthn.getCredentials` while running, seal with `age --passphrase` under a PIN typed at launch, re-inject on next launch. Sign counts must be written back on exit.
- age refuses passphrases from pipes: run it with a private pty as controlling terminal (setsid + TIOCSCTTY) and type the PIN into the master. The responder thread MUST be stopped (Event + join) BEFORE closing master_fd, else `OSError: Bad file descriptor`.
- Close with `Browser.close` over the pipe and wait for the profile's SingletonLock owners to exit, or the next launch fails ("Chrome instance exited").

## Presence / touch control
- Chromium decides user presence when a request STARTS; flipping `setAutomaticPresenceSimulation` on an already-waiting request does nothing. To make a terminal keypress the touch: set `automaticPresenceSimulation:false`, inject (via `Page.addScriptToEvaluateOnNewDocument`) a script wrapping `navigator.credentials.create/get` that awaits a gate promise, then on keypress: presence ON -> release gate -> wait until in-flight==0 -> presence OFF.
- Keys: `.` = touch (cbreak mode, no Enter), Enter = unplug/plug.

## Unplug => phone QR
- Unplug = `WebAuthn.removeVirtualAuthenticator` AND `WebAuthn.disable`. Removing alone leaves Chromium hanging with no dialog; disabling the environment brings back the normal "Passkeys & Security Keys" dialog with QR. QR/hybrid needs real Bluetooth; Chromium's virtual mode disables real transports, so QR only works while unplugged.
- A request left on the QR dialog stays stuck and later requests fail with `OperationError` until the page reloads. On re-plug, reload only if a request reached Chromium (in-flight and not merely held by the gate); a reload loses typed form text.
- The gate script must be re-registered (remove old identifier, add new) on every plug/unplug so new documents start in the right state, and `window.__vykeyHold` toggled for the current document.

## Testing tips
- Test pages must be on `localhost` (secure context); `data:` URLs throw TypeError. Start page servers as managed services; `&`-backgrounded servers die with the tool shell.
- With the pipe transport there is no second DevTools client, so drive the test page by polling a command queue from the page itself, or test via the `Browser` class in-process.
- sudo here uses fingerprint: `sudo -n` fails; ask the user to run `sudo -v` in their terminal.

## Unverified
- Not confirmed on chatgpt.com/auth.openai.com (Cloudflare "Verify you are human" appeared with the chromedriver build; clearing `chromium-profile` and a manual click may be needed) or Apple. Attestation requirements may reject virtual keys.
- Leftover unused artifacts the user may want removed: /etc/udev/rules.d/99-virtual-yubikey.rules, dummy_hcd gadget, /tmp/swytoken/*.
