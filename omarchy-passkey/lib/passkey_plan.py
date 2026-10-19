"""Decide what a sync must do. Pure: takes two sets of passkeys, returns actions.

Identity is the credential id. Two sides can hold the same id with different
state; the only state that ever changes is the signature counter, which only
grows, so the higher counter wins. Nothing here deletes: a missing credential on
one side is copied over, never removed. Deletion is a deliberate user action in
Bitwarden or `passless client`, not something a sync may infer from absence
(that would turn one failed vault read into data loss).
"""

from __future__ import annotations

from dataclasses import dataclass

from passkey_convert import Passkey


@dataclass(frozen=True)
class Plan:
    """What to do to reach agreement. Each tuple holds whole Passkeys to write."""

    pull: tuple[Passkey, ...]  # vault has it, local does not: write local
    push: tuple[Passkey, ...]  # local has it, vault does not: create vault item
    raise_vault_counter: tuple[Passkey, ...]  # local counter is higher: update vault
    raise_local_counter: tuple[Passkey, ...]  # vault counter is higher: update local
    conflicts: tuple[tuple[Passkey, Passkey], ...]  # same id, different key: (local, vault)

    @property
    def is_noop(self) -> bool:
        return not (
            self.pull
            or self.push
            or self.raise_vault_counter
            or self.raise_local_counter
            or self.conflicts
        )


def plan(local: list[Passkey], vault: list[Passkey]) -> Plan:
    """Compare both sides by credential id.

    Preconditions: ids are unique within each list (duplicates raise ValueError;
    a duplicate means the store is corrupt and guessing would lose a key).
    Postcondition: applying the returned actions makes every credential present
    on both sides with the larger counter, except `conflicts`, which the caller
    must surface and not touch.
    """
    local_by_id = _index(local, "local")
    vault_by_id = _index(vault, "vault")

    pull, push, up_vault, up_local, conflicts = [], [], [], [], []

    for cid, mine in local_by_id.items():
        theirs = vault_by_id.get(cid)
        if theirs is None:
            push.append(mine)
        elif mine.private_scalar != theirs.private_scalar or mine.rp_id != theirs.rp_id:
            conflicts.append((mine, theirs))
        elif mine.sign_count > theirs.sign_count:
            up_vault.append(mine)
        elif theirs.sign_count > mine.sign_count:
            up_local.append(theirs)

    for cid, theirs in vault_by_id.items():
        if cid not in local_by_id:
            pull.append(theirs)

    return Plan(
        tuple(pull), tuple(push), tuple(up_vault), tuple(up_local), tuple(conflicts)
    )


def _index(passkeys: list[Passkey], side: str) -> dict[bytes, Passkey]:
    by_id: dict[bytes, Passkey] = {}
    for passkey in passkeys:
        if passkey.credential_id in by_id:
            raise ValueError(
                f"duplicate credential id on {side} side: {passkey.credential_id.hex()}"
            )
        by_id[passkey.credential_id] = passkey
    return by_id
