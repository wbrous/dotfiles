import dataclasses
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import bw_vault as bv
import passkey_convert as pc
import passkey_store as ps
import passkey_sync as sync
from test_bw_vault import FakeServer, login_with
from test_passkey_convert import a_passkey


class Sync(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "store"

    def vault_of(self, *passkeys):
        server = FakeServer([login_with(p, f"item-{i}") for i, p in enumerate(passkeys)])
        return bv.Vault(server), server

    # If this fails: a new machine does not get the user's passkeys at login.
    def test_pull_populates_an_empty_store_from_the_vault(self):
        a, b = a_passkey(), a_passkey()
        vault, _ = self.vault_of(a, b)
        result = sync.pull(vault, self.root)
        self.assertEqual(result.pulled, 2)
        self.assertEqual({p.credential_id for p in ps.read_all(self.root)}, {a.credential_id, b.credential_id})

    # If this fails: pull modifies the vault, which it must never do (it runs
    # unattended at login against the user's real passwords).
    def test_pull_never_writes_to_the_vault(self):
        ps.write(self.root, a_passkey())  # local-only: push would create an item
        vault, server = self.vault_of(a_passkey())
        sync.pull(vault, self.root)
        self.assertEqual([c for c in server.calls if c[0] in ("POST", "PUT", "DELETE")], [])

    # If this fails: push modifies the local store, racing with the running daemon.
    def test_push_never_writes_the_local_store(self):
        ps.write(self.root, a_passkey())
        before = {p: p.stat().st_mtime_ns for p in self.root.rglob("*.bin")}
        vault, _ = self.vault_of(a_passkey())
        sync.push(vault, self.root)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.root.rglob("*.bin")})

    # If this fails: a passkey registered on this machine is not backed up,
    # and is lost at reboot because the store lives in RAM.
    def test_push_creates_vault_items_for_new_local_credentials(self):
        a = a_passkey()
        ps.write(self.root, a)
        vault, _ = self.vault_of()
        self.assertEqual(sync.push(vault, self.root).pushed, 1)
        self.assertEqual([p for _, p in vault.list_passkeys()], [a])

    # If this fails: running the sync twice (e.g. a retry after a crash) creates
    # duplicate vault items for the same passkey.
    def test_push_twice_does_not_duplicate(self):
        ps.write(self.root, a_passkey())
        vault, server = self.vault_of()
        sync.push(vault, self.root)
        again = sync.push(vault, self.root)
        self.assertEqual(again.pushed, 0)
        self.assertEqual(len(server.items), 1)

    # If this fails: signing a login on this machine never advances the counter
    # in the vault, so another device sees a stale counter.
    def test_push_raises_vault_counter_when_local_is_ahead(self):
        a = a_passkey(sign_count=1)
        vault, _ = self.vault_of(a)
        ps.write(self.root, dataclasses.replace(a, sign_count=7))
        self.assertEqual(sync.push(vault, self.root).counters_raised_in_vault, 1)
        self.assertEqual(vault.list_passkeys()[0][1].sign_count, 7)

    # If this fails: a counter used on another device is ignored here, and
    # the next login sends a lower counter (looks like a cloned key).
    def test_pull_raises_local_counter_when_vault_is_ahead(self):
        a = a_passkey(sign_count=1)
        ps.write(self.root, a)
        vault, _ = self.vault_of(dataclasses.replace(a, sign_count=9))
        self.assertEqual(sync.pull(vault, self.root).counters_raised_locally, 1)
        self.assertEqual(ps.read_all(self.root)[0].sign_count, 9)

    # If this fails: a key collision is "resolved" silently, overwriting a
    # private key in one place.
    def test_key_collision_stops_the_sync_and_changes_nothing(self):
        mine = a_passkey()
        ps.write(self.root, mine)
        theirs = dataclasses.replace(mine, private_scalar=a_passkey().private_scalar)
        vault, server = self.vault_of(theirs)
        for operation in (sync.pull, sync.push):
            with self.assertRaises(sync.SyncConflict):
                operation(vault, self.root)
        self.assertEqual(ps.read_all(self.root), [mine])
        self.assertEqual([p for _, p in vault.list_passkeys()], [theirs])

    # If this fails: a locked vault makes the sync "succeed" having done nothing,
    # so the user believes they are backed up.
    def test_locked_vault_is_an_error_not_a_noop(self):
        ps.write(self.root, a_passkey())
        vault = bv.Vault(FakeServer(locked=True))
        for operation in (sync.pull, sync.push):
            with self.assertRaises(bv.VaultLocked):
                operation(vault, self.root)

    # If this fails: a passkey that Bitwarden holds but we cannot use (non-P-256)
    # is silently ignored with no trace for the user.
    def test_unsupported_vault_passkeys_are_reported(self):
        foreign = pc.passkey_to_bitwarden(a_passkey())
        foreign["keyCurve"] = "P-384"
        server = FakeServer([{"id": "x", "type": 1, "name": "Odd", "login": {"fido2Credentials": [foreign]}}])
        result = sync.pull(bv.Vault(server), self.root)
        self.assertEqual(len(result.skipped_in_vault), 1)

    # If this fails: after a full pull+push cycle the two sides still differ, so
    # every login re-syncs the same credentials.
    def test_sides_agree_after_pull_then_push(self):
        a, b, c = a_passkey(sign_count=1), a_passkey(sign_count=2), a_passkey(sign_count=3)
        ps.write(self.root, a)
        ps.write(self.root, dataclasses.replace(b, sign_count=8))
        vault, _ = self.vault_of(b, c)
        sync.pull(vault, self.root)
        sync.push(vault, self.root)
        local = {p.credential_id: p.sign_count for p in ps.read_all(self.root)}
        remote = {p.credential_id: p.sign_count for _, p in vault.list_passkeys()}
        self.assertEqual(local, remote)
        self.assertEqual(len(local), 3)


if __name__ == "__main__":
    unittest.main()
