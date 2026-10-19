"""Apply a sync between the local passless store and the Bitwarden vault.

Two entry points, matching when the daemon may touch the store:

  pull(vault, root)   Run BEFORE passless starts. Writes vault-only credentials
                      and higher vault counters into the store.
  push(vault, root)   Run whenever passless has registered something. Creates vault
                      items for local-only credentials and raises vault counters.

passless reads its directory once at startup, so pull is only effective before it
starts, and push is safe at any time because it only reads the local store.

Failure policy: nothing is swallowed. A vault or store error propagates after
already-completed steps are kept (each step is independently valid and the plan
is idempotent, so re-running finishes the job). A push that fails leaves the
credential only in the RAM-backed store, so the caller must treat a PushError as
"this passkey is NOT backed up yet".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import passkey_store
from bw_vault import Vault
from passkey_plan import Plan, plan


class SyncConflict(RuntimeError):
    """Same credential id with different key material on the two sides."""


@dataclass(frozen=True)
class Result:
    pulled: int
    pushed: int
    counters_raised_in_vault: int
    counters_raised_locally: int
    skipped_in_vault: tuple[str, ...]


def _plan(vault: Vault, root: Path) -> tuple[Plan, dict[bytes, str]]:
    """Read both sides and plan. Returns the plan and vault item id by credential id."""
    vault_entries = vault.list_passkeys()
    local = passkey_store.read_all(root)
    the_plan = plan(local, [p for _, p in vault_entries])
    if the_plan.conflicts:
        ids = ", ".join(local_side.credential_id.hex()[:12] for local_side, _ in the_plan.conflicts)
        raise SyncConflict(f"credential id collision with different keys: {ids}")
    return the_plan, {p.credential_id: item_id for item_id, p in vault_entries}


def pull(vault: Vault, root: Path) -> Result:
    """Bring vault state into the local store. Never writes to the vault."""
    the_plan, _ = _plan(vault, root)
    for passkey in the_plan.pull + the_plan.raise_local_counter:
        passkey_store.write(root, passkey)
    return Result(
        pulled=len(the_plan.pull),
        pushed=0,
        counters_raised_in_vault=0,
        counters_raised_locally=len(the_plan.raise_local_counter),
        skipped_in_vault=tuple(vault.skipped),
    )


def push(vault: Vault, root: Path) -> Result:
    """Bring local state into the vault. Never writes to the local store."""
    the_plan, item_ids = _plan(vault, root)
    for passkey in the_plan.push:
        vault.create_passkey_item(passkey)
    for passkey in the_plan.raise_vault_counter:
        vault.set_counter(item_ids[passkey.credential_id], passkey)
    return Result(
        pulled=0,
        pushed=len(the_plan.push),
        counters_raised_in_vault=len(the_plan.raise_vault_counter),
        counters_raised_locally=0,
        skipped_in_vault=tuple(vault.skipped),
    )
