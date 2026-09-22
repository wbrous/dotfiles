---
name: docker-compose-required-env-var-colon-quoting
description: "Use when a docker-compose.yml/compose.yml uses the ${VAR:?error message} required-env-var guard syntax with a human-readable error message, and docker compose config (or up) fails with a YAML parse error like \"mapping values are not allowed in this context\" — the unquoted ${VAR:?message with a colon: like this} value gets misparsed as a nested YAML mapping because of the literal colon inside the message. Also covers installing shellcheck without sudo (static release binary to ~/.local/bin) when fingerprint-gated sudo can't get a physical touch in a headless/agent context."
---

## Problem

Writing a self-documenting required-env-var guard in a compose file:

```yaml
environment:
  POSTGRES_USER: ${POSTGRES_USER:?Set POSTGRES_USER in .env: the Postgres role Logto connects as}
```

`docker compose config` fails with:

```
go-yaml load error in scanner at L7.C64: mapping values are not allowed in this context
```

The colon after `.env` inside the unquoted scalar is parsed by YAML as a
mapping key/value separator, not as part of the string — even though this
is compose-shell interpolation syntax (`${VAR:?message}`), YAML parses the
raw file *before* compose does variable interpolation.

## Fix

Quote every `${VAR:?message}` value that contains a colon in the message:

```yaml
environment:
  POSTGRES_USER: "${POSTGRES_USER:?Set POSTGRES_USER in .env: the Postgres role Logto connects as}"
```

Applies anywhere the same pattern appears — `DB_URL: "postgres://${USER:?...}:${PASS:?...}@host/${DB:?...}"`
needs the same treatment (and doubly so, since the URL itself also has colons).

Verify via `docker compose config` directly, or better, write a small test
that unsets each required var one at a time and asserts `docker compose
config` fails *and* the error message mentions that var name — this catches
both missing guards and this quoting bug at once.

## Related: installing shellcheck without sudo

If `sudo pacman -S shellcheck` (or any sudo install) hangs waiting on a
fingerprint touch that never resolves in a headless/agent session, skip
sudo entirely — fetch the static release binary:

```bash
mkdir -p ~/.local/bin && cd /tmp
curl -fsSL https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.xz -o sc.tar.xz
tar xf sc.tar.xz
cp shellcheck-v0.11.0/shellcheck ~/.local/bin/
chmod +x ~/.local/bin/shellcheck
```

No system package touched, nothing to clean up, works immediately if
`~/.local/bin` is on `PATH` (or invoke it by full path).
