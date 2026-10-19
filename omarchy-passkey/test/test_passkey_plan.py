import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import passkey_plan as pp
from test_passkey_convert import a_passkey


def with_counter(passkey, counter):
    return dataclasses.replace(passkey, sign_count=counter)


class Plan(unittest.TestCase):
    # If this fails: a sync of identical stores does work, rewriting vault
    # items every time the daemon starts.
    def test_identical_sides_need_nothing(self):
        a, b = a_passkey(), a_passkey()
        self.assertTrue(pp.plan([a, b], [b, a]).is_noop)

    # If this fails: a passkey made while offline never reaches the vault.
    def test_local_only_credential_is_pushed(self):
        a = a_passkey()
        result = pp.plan([a], [])
        self.assertEqual(result.push, (a,))
        self.assertEqual(result.pull, ())

    # If this fails: a passkey saved on another device never reaches this machine.
    def test_vault_only_credential_is_pulled(self):
        a = a_passkey()
        result = pp.plan([], [a])
        self.assertEqual(result.pull, (a,))
        self.assertEqual(result.push, ())

    # If this fails: the counter goes backwards, which relying parties treat as
    # a cloned authenticator and may lock the account.
    def test_higher_counter_wins_in_both_directions(self):
        base = a_passkey(sign_count=5)
        ahead_local = pp.plan([with_counter(base, 9)], [base])
        self.assertEqual(ahead_local.raise_vault_counter, (with_counter(base, 9),))
        self.assertEqual(ahead_local.raise_local_counter, ())
        ahead_vault = pp.plan([base], [with_counter(base, 9)])
        self.assertEqual(ahead_vault.raise_local_counter, (with_counter(base, 9),))
        self.assertEqual(ahead_vault.raise_vault_counter, ())

    # If this fails: an empty or failed vault read is treated as "user deleted
    # everything". Whatever one side lacks, the other side's credentials must
    # all be kept and carried over, never dropped.
    def test_a_side_that_lacks_everything_loses_nothing(self):
        creds = [a_passkey(), a_passkey(), a_passkey()]
        to_vault = pp.plan(creds, [])
        self.assertEqual(set(p.credential_id for p in to_vault.push), set(p.credential_id for p in creds))
        to_local = pp.plan([], creds)
        self.assertEqual(set(p.credential_id for p in to_local.pull), set(p.credential_id for p in creds))

    # If this fails: two different keys sharing an id are merged, silently
    # replacing one private key with the other.
    def test_same_id_different_key_is_a_conflict_and_untouched(self):
        mine = a_passkey()
        theirs = dataclasses.replace(mine, private_scalar=a_passkey().private_scalar)
        result = pp.plan([mine], [theirs])
        self.assertEqual(result.conflicts, ((mine, theirs),))
        self.assertEqual(
            (result.pull, result.push, result.raise_local_counter, result.raise_vault_counter),
            ((), (), (), ()),
        )

    # If this fails: a credential for one site is overwritten by another's id match.
    def test_same_id_different_rp_is_a_conflict(self):
        mine = a_passkey()
        theirs = dataclasses.replace(mine, rp_id="other.example")
        self.assertEqual(len(pp.plan([mine], [theirs]).conflicts), 1)

    # If this fails: a corrupt store with a duplicated id is resolved by
    # whichever copy happens to be read last.
    def test_duplicate_ids_on_one_side_crash(self):
        a = a_passkey()
        for local, vault in (([a, a], []), ([], [a, a])):
            with self.assertRaises(ValueError):
                pp.plan(local, vault)

    # If this fails: applying the plan twice is not idempotent, so a retry
    # after a partial failure duplicates items in the vault.
    def test_plan_is_empty_after_applying_it(self):
        a, b, c = a_passkey(sign_count=1), a_passkey(sign_count=2), a_passkey(sign_count=3)
        local = [a, with_counter(b, 8)]
        vault = [with_counter(b, 2), c]
        result = pp.plan(local, vault)
        merged_local = {p.credential_id: p for p in local}
        merged_vault = {p.credential_id: p for p in vault}
        for p in result.pull + result.raise_local_counter:
            merged_local[p.credential_id] = p
        for p in result.push + result.raise_vault_counter:
            merged_vault[p.credential_id] = p
        self.assertTrue(pp.plan(list(merged_local.values()), list(merged_vault.values())).is_noop)


if __name__ == "__main__":
    unittest.main()
