---
name: chromium-virtual-webauthn-security-key
description: "User wants a fake/software YubiKey or security key for a website (e.g. ChatGPT, Apple) on Linux without hardware; Chromium virtual WebAuthn authenticator driven over --remote-debugging-pipe, PIN-sealed credentials, terminal touch key, tab/iframe gating."
---

# Software security key via Chromium's virtual authenticator

## Decision: do NOT emulate USB
- Laptop xHCI ports are host-only. No UDC, so no USB gadget; Limine/boot config and cables cannot change that.
- `dummy_hcd` gives a UDC and a gadget enumerates as 1050:0407, but it needs `f_hidg` (absent on Arch/omarchy kernels) plus a CTAP2 responder. Dead end for browsers; also invisible to ykman/sudo.
- Use Chromium CDP `WebAuthn.addVirtualAuthenticator` (ctap2, usb, resident key, UV). Sites see a USB security key. Only works in the Chromium instance you drive (dedicated profile).

## Transport
- Drive Chromium with `--remote-debugging-pipe` (fds 3 read / 4 write, NUL-delimited JSON), NOT chromedriver: chromedriver injects `cdc_*` globals and Cloudflare flags it.
- Add `--disable-blink-features=AutomationControlled` or navigator.webdriver is true under the pipe.
- chromedriver `/goog/cdp/execute` takes `params` (not `parameters`) and needs `WebAuthn.enable` first.
- Close with `Browser.close`, then wait until no process has the `--user-data-dir`; killing the driver orphans Chromium and leaves SingletonLock.

## Persistence
- Authenticator lives in browser memory only. Persist `WebAuthn.getCredentials` output sealed with `age --passphrase` (PIN). age reads passphrases only from a tty: give it a private pty (setsid + TIOCSCTTY) and type the PIN.
- Stop the pty responder thread (Event + join, no timeout) BEFORE closing the master fd, else `OSError EBADF` in select.
- Sign counter must only go up: merge by credentialId keeping highest signCount.

## Touch on demand / plug-unplug
- `automaticPresenceSimulation` is decided when a request STARTS; enabling it on a pending request does nothing. So wrap `navigator.credentials.create/get` (Page.addScriptToEvaluateOnNewDocument) to hold the call, then on keypress: presence on -> release held call -> wait until settled -> presence off.
- Unplug = `removeVirtualAuthenticator` + `WebAuthn.disable`; Chromium then shows its own dialog with the phone QR (needs Bluetooth, and the virtual environment off). Removing only the authenticator leaves requests hanging with no dialog.
- Re-plug while a request is stuck on the QR dialog: Chromium rejects new requests (OperationError) until the page reloads. Reload only if a request is in flight and not merely held.
- Gate script must start in the right state for the key (build it with a `hold` arg, re-register on plug/unplug).

## Tabs, popups, iframes (the real ChatGPT/Apple failure)
- The gate and key only on the first tab = request goes straight to Chromium's "Insert your security key" dialog and the terminal says nothing is waiting.
- Use BROWSER-level `Target.setAutoAttach {autoAttach, waitForDebuggerOnStart:true, flatten:true}` (session None) so every tab/popup/iframe arrives frozen; also set it per session for child frames.
- Authenticators are per-TAB (WebAuthn.enable and ids are session-scoped; no browser-wide domain). Keep one authenticator per tab, sync credentials across tabs after each touch, seed late tabs on the main-loop tick, restore on plug.
- Resume EVERY attached target (`Runtime.runIfWaitingForDebugger`) including service workers/extensions/browser UI, or they stay frozen.
- Deadlock trap: a page can open a tab in the middle of a command (window.open inside Runtime.evaluate). Handle attach events inside the `_send` wait loop using WRITE-ONLY `_post` commands (gate script -> enable/add authenticator -> resume, in pipe order). Never nest `_send` from an event handler: the inner wait swallows the outer reply and startup times out.
- A tab's authenticator id arrives only in the reply, so record pending ids in `_file_incoming`.

## Terminal UX
- cbreak mode (termios/tty.setcbreak) so `.` works without Enter; Enter toggles plug/unplug; print `\r` in cbreak. Restore terminal in finally.

## Verifying
- Never test on the real site first: serve local pages (managed service; background `&` servers die with the shell) and drive them via CDP. Check: held not auto-answered, touch completes, presence drops after, same credential after re-plug and after full restart, no Chromium left behind.
- Cross-origin iframe test needs different hostnames (localhost vs 127.0.0.1) or you get SecurityError.
- Edit tool: ranges from `read path:a,b` return anchors only; always read a contiguous range before editing.

## Cloudflare note
- Bot challenge may still appear; clear `chromium-profile` once, then click the checkbox by hand. Do not spoof UA/GPU/canvas.
- sudo here uses fingerprint; run privileged steps in the user's own terminal when the harness has no tty.
