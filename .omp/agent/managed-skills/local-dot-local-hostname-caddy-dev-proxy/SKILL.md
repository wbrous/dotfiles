---
name: local-dot-local-hostname-caddy-dev-proxy
description: "Use when setting up a temporary local reverse-proxy setup so a browser can reach services via friendly hostnames like foo.local / foo-admin.local instead of localhost:PORT — especially for testing a multi-service app (e.g. Logto: public app + admin console) where one service's Admin/Web-Crypto UI requires a secure context. Also covers the systemd/Arch nsswitch.conf gotcha where .local hostnames in /etc/hosts are silently ignored because mdns_minimal is queried before files."
---

## Problem

Want to hit `http://foo.local` / `https://foo-admin.local` in a browser during local testing instead of remembering ports, without any permanent system changes.

## Gotcha: `.local` hostnames in `/etc/hosts` can be silently ignored

On many systemd-based distros (confirmed on Arch/Omarchy), `/etc/nsswitch.conf` has:

```
hosts: mymachines mdns_minimal [NOTFOUND=return] resolve files myhostname dns
```

`mdns_minimal` is queried *before* `files`, and `[NOTFOUND=return]` means: if mDNS says "not found," resolution **stops immediately** — `/etc/hosts` (`files`) is never even reached for `.local` names. Symptom: `getent hosts foo.local` returns nothing, `curl http://foo.local` gets connection refused/timeout, even though `/etc/hosts` clearly has the entry and manually setting `Host: foo.local` against `127.0.0.1` works fine.

Fix (temporary, revert after testing): back up and reorder `/etc/nsswitch.conf` so `files` comes first:

```bash
sudo sh -c 'cp /etc/nsswitch.conf /etc/nsswitch.conf.TESTNAME-backup && \
  sed -i "s/^hosts:.*/hosts: files mymachines resolve myhostname mdns_minimal [NOTFOUND=return] dns/" /etc/nsswitch.conf'
```

Revert on cleanup: `sudo cp /etc/nsswitch.conf.TESTNAME-backup /etc/nsswitch.conf`.

This requires sudo — on a fingerprint-gated system this needs the user physically present to touch the sensor; a stuck prompt (fingerprint timeout falling through to a password prompt with no password available) must be stopped and retried once the user confirms they'll accept it (see `sudo-interactive-tty-via-hub`).

## Recipe: Caddy as a zero-permanent-footprint local reverse proxy

1. Add `127.0.0.1 foo.local foo-admin.local` to `/etc/hosts` (sudo, see above).
2. Fix nsswitch order if `.local` resolution silently fails (see above).
3. Download a static Caddy binary to `~/.local/bin/caddy` (no sudo, no package manager):
   ```bash
   curl -sL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o ~/.local/bin/caddy
   chmod +x ~/.local/bin/caddy
   ```
4. Write a scratch Caddyfile (e.g. `/tmp/foo-local-test/Caddyfile`) using **non-privileged ports** (8080/8443 or similar) to avoid needing sudo to bind 80/443 — but first check the chosen port isn't already taken by something else on the box (`ss -ltn | grep :8080`); if it is, just pick another (18080/18443 worked fine).
5. **Critical:** if any site block uses `https://`, Caddy's `auto_https` feature will try to also bind port 80 for an HTTP→HTTPS redirect, even though nothing asked for port 80 — this fails with `permission denied` for a non-root process. Disable it globally:
   ```caddyfile
   {
       auto_https disable_redirects
   }

   http://foo.local:18080 {
       reverse_proxy 127.0.0.1:PORT_A
   }

   https://foo-admin.local:18443 {
       tls internal
       reverse_proxy 127.0.0.1:PORT_B
   }
   ```
   `tls internal` uses Caddy's own local CA to self-sign — browser will show a one-time warning to click through; no system trust-store install needed for casual testing.
6. Run via a supervised background process (e.g. `hub start`), non-persistent, so it's cleaned up automatically when the session ends — matches a "temporary, not permanent" ask.
7. Use `ready: {"log": "server running", "port": 18080, ...}` (or similar) to confirm Caddy actually bound before moving on.

## Docker container secure-context / self-call gotcha (generalizes beyond Logto)

If the backend service you're proxying makes its own internal HTTP self-calls to its configured public "ENDPOINT"/base-URL (common in OIDC providers, webhooks-validators, etc.), and that ENDPOINT is now `http://foo.local:PORT` instead of `localhost`, the **container itself** needs to be able to resolve `foo.local` and reach the host's Caddy — the container's own DNS doesn't know about your host's `/etc/hosts`. Fix via a Compose override (don't touch the real `compose.yml` for a temporary test):

```yaml
services:
  app:
    extra_hosts:
      - "foo.local:host-gateway"
```

`host-gateway` is a Docker magic value that resolves to the host's own IP from inside the container network (works on Linux too, Docker 20.10+). Caddy must be listening on all interfaces (default for a bare `hostname:port` address in a Caddyfile) — not just `127.0.0.1` — so the container's bridge-network request can actually reach it.

Separately: browsers only grant the Web Crypto API (`crypto.subtle`) to a secure context — HTTPS, or HTTP on literal `localhost`. A custom hostname like `foo-admin.local` over plain HTTP will silently break any UI that needs it (e.g. Logto's Admin Console). Self-signed HTTPS via `tls internal` is sufficient — the browser only shows a trust warning, `crypto.subtle` still works once you click through.

## Cleanup checklist for a temporary setup like this

- Stop the Caddy background process.
- `docker compose down -v` the stack.
- Remove the added `/etc/hosts` lines.
- Restore `/etc/nsswitch.conf` from the backup, if it was changed.
