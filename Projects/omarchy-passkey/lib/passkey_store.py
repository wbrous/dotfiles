"""Read and write passless's `local` backend directory: `<root>/<rpId>/<hex id>.bin`.

Contract:
- Files are written 0600 in 0700 directories, atomically (temp file + rename),
  matching what passless itself does, so a crash never leaves a half file that
  passless would reject at startup.
- passless indexes the directory once at startup and never rescans, so writes
  are only seen after the daemon restarts. Callers must not expect a live daemon
  to notice them.
- A file that cannot be parsed raises StoreError. Skipping it would let a sync
  conclude the credential is absent and overwrite it with the vault's copy.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from passkey_convert import (
    ConversionError,
    Passkey,
    cbor_decode,
    cbor_encode,
    passkey_from_passless,
    passless_from_passkey,
)

EXTENSION = ".bin"


class StoreError(RuntimeError):
    """The local credential directory holds something we cannot interpret."""


def filename_for(passkey: Passkey) -> str:
    """`<rpId>/<hex credential id>.bin`, relative to the store root."""
    _check_rp_dir(passkey.rp_id)
    return f"{passkey.rp_id}/{passkey.credential_id.hex()}{EXTENSION}"


def _check_rp_dir(rp_id: str) -> None:
    """Refuse an rpId that would escape the store or break the layout.

    rpIds come from relying parties, i.e. from the network, and from the vault.
    """
    if not rp_id or rp_id in (".", "..") or "/" in rp_id or "\\" in rp_id or "\0" in rp_id:
        raise StoreError(f"unsafe rpId for a directory name: {rp_id!r}")


def read_all(root: Path) -> list[Passkey]:
    """Every credential under `root`. Missing root means an empty store."""
    if not root.exists():
        return []
    found = []
    for path in sorted(root.glob(f"*/*{EXTENSION}")):
        try:
            record = cbor_decode(path.read_bytes())
            passkey = passkey_from_passless(record)
        except (ConversionError, OSError) as exc:
            raise StoreError(f"{path}: {exc}") from exc
        if path.relative_to(root).as_posix() != filename_for(passkey):
            raise StoreError(f"{path}: filename does not match the credential inside it")
        found.append(passkey)
    return found


def write(root: Path, passkey: Passkey) -> Path:
    """Write (or overwrite) one credential. Returns the file path."""
    target = root / filename_for(passkey)
    _make_private_dir(root)
    _make_private_dir(target.parent)
    payload = cbor_encode(passless_from_passkey(passkey))
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
    return target


def _make_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise StoreError(f"{path} is accessible to other users (mode {path.stat().st_mode & 0o777:o})")
