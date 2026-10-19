# omarchy-passkey

Virtual FIDO2 security key for Omarchy, with Bitwarden as the durable store.

- **Authenticator**: the [wbrous/passless](https://github.com/wbrous/passless)
  fork (release `0.20.2-omarchy.1`), a virtual UHID security key browsers and
  native apps talk to like hardware. The fork is required: upstream ignores
  `enable_credential_backup`, so every passkey registers BE=0 while Bitwarden
  reports BE=1 and strict sites reject it.
- **Durable copy**: Bitwarden. A watcher backs up each new passkey as created;
  passkeys are decrypted only in RAM (`$XDG_RUNTIME_DIR`).
- **Unlock**: `bw` session comes from a root-owned helper gated by a
  fingerprint polkit prompt — the master password is never typed at login and
  never visible to the user session.

## Layout

- `bin/omarchy-install-service-passkeys` — installer (downloads the fork
  binary with pinned SHA-256, installs root-owned helpers + polkit policy,
  udev rule, enables services).
- `bin/omarchy-remove-service-passkeys` — removes all of the above; passkeys
  stay in the vault.
- `bin/omarchy-passkey-{start,sync,unlock,watch}` — service entry points.
- `lib/` — sync bridge (`bw serve` ↔ passless store).
- `libexec/omarchy-passkey-{enroll,unlock}-root` — root-owned helpers.
- `default/systemd/user/` — the three user units.
- `polkit/` — fingerprint-gated unlock policy.
- `test/` — unit tests + e2e scripts.

## Install

```sh
sudo bin/omarchy-install-service-passkeys
# 1. log out/in (fido group), 2. bw login, 3. sudo /usr/lib/omarchy-passkey/omarchy-passkey-enroll-root
```

## Test

```sh
python3 -m unittest discover -s test
```
