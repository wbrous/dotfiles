"""Where the passkey services keep their runtime state. One definition for everyone.

All of it lives under $XDG_RUNTIME_DIR/omarchy-passkey (tmpfs, mode 700, owned by
the user), so decrypted credentials never touch disk and no other user can reach
the vault socket. The root unlock helper recomputes the socket path from the
invoking uid on its own (it must not trust the caller's environment), so
`socket_path_for_uid` is the one formula both sides must agree on.
"""

from __future__ import annotations

import os
from pathlib import Path


def socket_path_for_uid(uid: int) -> str:
    """The bw serve socket for `uid`. Matches the root helper's own derivation."""
    return f"/run/user/{uid}/omarchy-passkey/bw.sock"


def runtime_dir() -> Path:
    """$XDG_RUNTIME_DIR/omarchy-passkey. Raises if there is no runtime dir.

    Failing is deliberate: falling back to /tmp would put decrypted private keys on
    a world-traversable, possibly disk-backed path.
    """
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise RuntimeError("XDG_RUNTIME_DIR is not set; refusing to use a fallback location")
    return Path(base) / "omarchy-passkey"


def vault_socket() -> str:
    """The bw serve socket to talk to. Overridable only for tests."""
    return os.environ.get("OMARCHY_PASSKEY_BW_SOCKET") or str(runtime_dir() / "bw.sock")


def store_dir() -> Path:
    """The decrypted credential store. Overridable only for tests."""
    override = os.environ.get("OMARCHY_PASSKEY_STORE")
    return Path(override) if override else runtime_dir() / "store"
