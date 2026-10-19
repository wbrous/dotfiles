import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import passkey_store as ps
from test_passkey_convert import a_passkey


class Store(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "store"

    # If this fails: a credential written by sync is not read back identically,
    # so the next sync sees a phantom difference and rewrites it forever.
    def test_write_then_read_roundtrips(self):
        a, b = a_passkey(rp_id="a.example"), a_passkey(rp_id="b.example")
        ps.write(self.root, a)
        ps.write(self.root, b)
        self.assertEqual({p.credential_id for p in ps.read_all(self.root)}, {a.credential_id, b.credential_id})
        self.assertIn(a, ps.read_all(self.root))

    # If this fails: private keys are readable by other local users.
    def test_files_and_dirs_are_private(self):
        path = ps.write(self.root, a_passkey())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    # If this fails: a pre-existing world-readable store is quietly reused and
    # keys are written into it.
    def test_refuses_a_store_dir_others_can_read(self):
        self.root.mkdir(mode=0o755)
        os.chmod(self.root, 0o755)
        with self.assertRaises(ps.StoreError):
            ps.write(self.root, a_passkey())

    # If this fails: a crash mid-write leaves a temp file that read_all later
    # treats as a credential (or as corrupt), blocking every sync.
    def test_leaves_no_temp_files_behind(self):
        ps.write(self.root, a_passkey())
        leftovers = [p.name for p in self.root.rglob("*") if p.is_file() and not p.name.endswith(".bin")]
        self.assertEqual(leftovers, [])

    # If this fails: re-syncing a higher counter creates a second file instead
    # of updating the credential, so passless sees two with one id.
    def test_overwrite_replaces_in_place(self):
        import dataclasses
        a = a_passkey(sign_count=1)
        ps.write(self.root, a)
        ps.write(self.root, dataclasses.replace(a, sign_count=5))
        (only,) = ps.read_all(self.root)
        self.assertEqual(only.sign_count, 5)

    # If this fails: a missing store is a crash on first run instead of empty.
    def test_missing_root_is_empty(self):
        self.assertEqual(ps.read_all(self.root / "nope"), [])

    # If this fails: a corrupt credential file is skipped, so sync thinks the
    # credential is absent and replaces it with the vault copy (data loss).
    def test_corrupt_file_raises_instead_of_being_skipped(self):
        path = ps.write(self.root, a_passkey())
        path.write_bytes(b"\xff\x00garbage")
        with self.assertRaises(ps.StoreError):
            ps.read_all(self.root)

    # If this fails: a file renamed or copied to the wrong place is trusted, and
    # an attacker or bug could shadow one site's credential with another's.
    def test_filename_must_match_contents(self):
        a = a_passkey(rp_id="a.example")
        path = ps.write(self.root, a)
        wrong = path.parent.parent / "b.example"
        wrong.mkdir(mode=0o700)
        path.rename(wrong / path.name)
        with self.assertRaises(ps.StoreError):
            ps.read_all(self.root)

    # If this fails: an rpId from the network/vault like "../x" writes outside
    # the store (path traversal into e.g. ~/.ssh).
    def test_unsafe_rp_ids_are_refused(self):
        for bad in ("", ".", "..", "../evil", "a/b", "a\\b", "x\0y"):
            with self.subTest(rp=bad):
                with self.assertRaises(ps.StoreError):
                    ps.write(self.root, a_passkey(rp_id=bad))
        self.assertFalse((Path(self._tmp.name) / "evil").exists())


if __name__ == "__main__":
    unittest.main()
