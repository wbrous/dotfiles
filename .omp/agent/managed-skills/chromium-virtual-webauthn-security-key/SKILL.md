---
name: chromium-virtual-webauthn-security-key
description: "Use for a fake/software YubiKey or security key for a website (e.g. ChatGPT), driving Chromium's WebAuthn virtual authenticator over CDP; not embedded browser. Critical: never edit AAGUID/authData bytes after Chromium signs them."
---

## Context

Chromium exposes `WebAuthn.addVirtualAuthenticator` over the DevTools protocol, letting you drive a page's `navigator.credentials.create()/get()` as if a real roaming security key were attached — no USB gadget hardware needed (laptop USB4/xHCI controllers are host-only; `/sys/class/udc` is empty; forget hardware-level spoofing, it's a dead end).

A full implementation (`vykey.py`) does this:
- `Target.setAutoAttach` + `waitForDebuggerOnStart` + `flatten` to gate every new tab/iframe before its first script runs
- `Page.addScriptToEvaluateOnNewDocument` installs a JS shim overriding `navigator.credentials.create/get` to gate on a terminal touch (Enter/`.` keypress) before calling through, and to patch the resulting credential's AAGUID
- Credentials sealed at rest with `age --passphrase`, PIN typed through a private pty (age refuses passphrases from a pipe)
- Single-threaded CDP command loop: one thread only ever calls `_send`/`touch()`, since two threads reading the same JSON-over-pipe connection race for replies

## Critical gotcha: never edit a signed attestation after the fact

Chromium's virtual authenticator's `MakeCredential` (`create()`) response is `fmt: "packed"`, **signed** by a fixed, well-known hardcoded "Chromium / Authenticator Attestation / Batch Certificate" key. The signature covers `authenticatorData` byte-for-byte (which embeds the 16-byte AAGUID at offset 37).

If you want the credential to claim a specific device identity (e.g. a real YubiKey AAGUID like `fa2b99dc-9e39-4257-8f92-4a30d23c4118` for "YubiKey 5 Series with NFC", from https://github.com/passkeydeveloper/passkey-authenticator-aaguids) **do not** byte-patch the AAGUID inside the already-signed `authData`/`attestationObject`. This silently produces a cryptographically invalid attestation. It will pass every local test you write yourself (byte search, roundtrip, decoding) because none of those verify the signature — but a real relying party that checks it (confirmed with OpenAI/ChatGPT: `passkey_verification_failed`, HTTP 400) will reject it outright.

**Prove this class of bug before shipping a WebAuthn credential mutation**: decode the real CBOR attestationObject, extract `attStmt.sig` and `attStmt.x5c[0]`, and verify the signature over `authData + sha256(clientDataJSON)` with `openssl pkeyutl -verify -pubin -inkey <(openssl x509 -in cert.der -inform der -noout -pubkey) -sigfile sig.der -rawin -digest sha256`. If you don't have a CBOR library available and can't install one (no sudo, no pip), hand-roll a ~40-line recursive CBOR decoder (majors 0/1/2/3/4/5/7 cover a WebAuthn attestationObject) rather than skip verification.

**Fix: rebuild as `fmt: "none"` instead of patching signed bytes.** `attStmt: {}` has no signature to invalidate, and this is the exact attestation downgrade real browsers perform when a site's conveyance preference doesn't require a full chain. Every WebAuthn server library reads the AAGUID from `authData` regardless of attestation format, so the device identity still shows up correctly, but there is no signature to break:

```js
function cborBytesHeader(len) {
  if (len < 24) return [0x40 | len];
  if (len < 256) return [0x58, len];
  if (len < 65536) return [0x59, (len >> 8) & 0xff, len & 0xff];
  return [0x5a, (len>>>24)&255, (len>>>16)&255, (len>>>8)&255, len&255];
}
function buildNoneAttestationObject(authData) {
  const head = [
    0xA3,
    0x63,0x66,0x6d,0x74,                               // "fmt"
    0x64,0x6e,0x6f,0x6e,0x65,                          // "none"
    0x67,0x61,0x74,0x74,0x53,0x74,0x6d,0x74,           // "attStmt"
    0xA0,                                                // {}
    0x68,0x61,0x75,0x74,0x68,0x44,0x61,0x74,0x61,      // "authData"
    ...cborBytesHeader(authData.length),
  ];
  const out = new Uint8Array(head.length + authData.length);
  out.set(head, 0); out.set(authData, head.length);
  return out.buffer;
}
// patch AAGUID in a *copy* of authData at offset 37 (16 bytes), then:
Object.defineProperty(resp, 'attestationObject', { value: buildNoneAttestationObject(patchedAuthData), configurable: true });
Object.defineProperty(resp, 'getAuthenticatorData', { value: () => patchedAuthData.buffer, configurable: true });
```

Chromium's internal authenticator store is unaffected by these JS-level property overrides on the returned `response` object — it still holds the real generated keypair/sign-counter, so later `get()` assertions against the same credential continue to work normally.

## Other pitfalls hit along the way

- **Site-specific attestation requirements are opaque until tested live.** You cannot infer from a generic 400 error alone whether the failure is attestation signature validation, AAGUID mismatch, or something else — get the actual failing request/response (e.g. from the user's browser devtools network tab or a captured curl) and decode it yourself rather than guessing.
- **`navigator.credentials` reads `undefined` on a page**: check `location.href` first — a `chrome-error://chromewebdata/` means the backing HTTP server for your test page wasn't actually up (race between starting it and loading), not a WebAuthn or secure-context bug.
- **Concurrent CDP calls from two threads deadlock/race.** If a test needs to simulate the terminal's `touch()` happening *during* an in-flight `create()`/`get()`, don't call `touch()` from a background thread while blocking on the browser reply in the main thread — fire the WebAuthn call without `awaitPromise`, poll a `window.__done` flag from the single main thread, call `touch()` from that same thread in between polls.
- **`pkill -9 -f <generic-substring>`** (e.g. `"chromium"`) kills every matching process on the machine, including unrelated running apps (Discord, Electron apps). Always scope kill patterns to your own test paths (profile dir, `VYKEY_DIR` value, a unique marker in the command line), never a bare technology name.
- Installing `cbor2`/`cryptography` via `pip` can fail entirely (`No module named pip`) in minimal environments, and `sudo pacman` needs an interactive password/fingerprint prompt that isn't always available — have a fallback (hand-rolled CBOR decoder, `openssl` CLI for signature verification) that needs no new dependencies.
