import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

import passkey_convert as pc


def a_scalar() -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_numbers().private_value.to_bytes(32, "big")


def a_passkey(**overrides) -> pc.Passkey:
    fields = dict(
        credential_id=os.urandom(32),
        rp_id="example.com",
        rp_name="Example",
        user_handle=os.urandom(16),
        user_name="alice",
        user_display_name="Alice A.",
        sign_count=7,
        discoverable=True,
        created=1_700_000_000,
        private_scalar=a_scalar(),
    )
    fields.update(overrides)
    return pc.Passkey(**fields)


def a_passless_record(**overrides) -> dict:
    record = pc.passless_from_passkey(a_passkey())
    record.update(overrides)
    return record


class KeyConversion(unittest.TestCase):
    # If this fails: a converted key no longer signs as the same identity, so
    # every relying party would reject the passkey after a vault round trip.
    def test_pkcs8_roundtrip_keeps_the_same_signing_key(self):
        scalar = a_scalar()
        recovered = pc.pkcs8_to_scalar(pc.scalar_to_pkcs8(scalar))
        self.assertEqual(recovered, scalar)

    # If this fails: PKCS#8 output is not what WebCrypto/Bitwarden can import,
    # so Bitwarden clients could not use passkeys we pushed.
    def test_pkcs8_output_loads_as_a_p256_key_with_matching_public_point(self):
        scalar = a_scalar()
        key = serialization.load_der_private_key(pc.scalar_to_pkcs8(scalar), password=None)
        self.assertIsInstance(key, ec.EllipticCurvePrivateKey)
        self.assertEqual(key.curve.name, "secp256r1")
        expected = ec.derive_private_key(int.from_bytes(scalar, "big"), ec.SECP256R1())
        self.assertEqual(
            key.public_key().public_numbers(), expected.public_key().public_numbers()
        )

    # If this fails: a signature made after conversion does not verify against
    # the public key the relying party registered.
    def test_signature_from_converted_key_verifies_against_original_public_key(self):
        original = ec.generate_private_key(ec.SECP256R1())
        scalar = original.private_numbers().private_value.to_bytes(32, "big")
        converted = serialization.load_der_private_key(
            pc.scalar_to_pkcs8(scalar), password=None
        )
        signature = converted.sign(b"challenge", ec.ECDSA(hashes.SHA256()))
        original.public_key().verify(signature, b"challenge", ec.ECDSA(hashes.SHA256()))
        with self.assertRaises(InvalidSignature):
            original.public_key().verify(signature, b"other", ec.ECDSA(hashes.SHA256()))

    # If this fails: a scalar with a leading zero byte loses it on the way
    # back, producing a 31-byte key that passless cannot load (1 in 256 keys).
    def test_scalar_with_leading_zero_byte_stays_32_bytes(self):
        scalar = b"\x00" + b"\x01" * 31
        self.assertEqual(pc.pkcs8_to_scalar(pc.scalar_to_pkcs8(scalar)), scalar)

    # If this fails: invalid key material is silently accepted instead of crashing.
    def test_rejects_bad_scalars(self):
        for bad in (b"", b"\x01" * 31, b"\x01" * 33, b"\x00" * 32):
            with self.subTest(length=len(bad), zero=set(bad) == {0}):
                with self.assertRaises(pc.ConversionError):
                    pc.scalar_to_pkcs8(bad)

    # If this fails: a non-P-256 key (RSA, other curve) is accepted and later
    # signs with the wrong algorithm.
    def test_rejects_non_p256_pkcs8(self):
        rsa_der = rsa.generate_private_key(65537, 2048).private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        p384_der = ec.generate_private_key(ec.SECP384R1()).private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        for der in (rsa_der, p384_der, b"garbage"):
            with self.assertRaises(pc.ConversionError):
                pc.pkcs8_to_scalar(der)


class CredentialIds(unittest.TestCase):
    # If this fails: a Bitwarden-minted UUID credential id changes on import,
    # so the relying party's stored id no longer matches.
    def test_16_byte_id_uses_uuid_form_and_roundtrips(self):
        raw = bytes(range(16))
        text = pc.credential_id_to_bitwarden(raw)
        self.assertEqual(text, "00010203-0405-0607-0809-0a0b0c0d0e0f")
        self.assertEqual(pc.credential_id_from_bitwarden(text), raw)

    # If this fails: passless's 32-byte ids get mangled; Bitwarden's
    # parseCredentialId only understands "b64." + base64url for non-UUID ids.
    def test_other_lengths_use_b64_prefix_and_roundtrip(self):
        for length in (1, 15, 17, 32, 64, 255):
            with self.subTest(length=length):
                raw = os.urandom(length)
                text = pc.credential_id_to_bitwarden(raw)
                self.assertTrue(text.startswith("b64."))
                self.assertNotIn("=", text)
                self.assertEqual(pc.credential_id_from_bitwarden(text), raw)

    # If this fails: ids of 15/16/17 bytes are confused with each other.
    def test_uuid_form_only_for_exactly_16_bytes(self):
        self.assertFalse(pc.credential_id_to_bitwarden(b"\x01" * 15).count("-"))
        self.assertEqual(pc.credential_id_to_bitwarden(b"\x01" * 16).count("-"), 4)
        self.assertFalse(pc.credential_id_to_bitwarden(b"\x01" * 17).count("-"))

    # If this fails: garbage ids are accepted and become an unusable credential.
    def test_rejects_unrecognised_and_empty_ids(self):
        for bad in ("", "not-a-uuid", "b64.", "b64.!!!", "0001020304050607"):
            with self.subTest(bad=bad):
                with self.assertRaises(pc.ConversionError):
                    pc.credential_id_from_bitwarden(bad)
        with self.assertRaises(pc.ConversionError):
            pc.credential_id_to_bitwarden(b"")

    # If this fails: uppercase UUIDs (valid, produced by some clients) are rejected.
    def test_uppercase_uuid_is_accepted(self):
        text = "AABBCCDD-EEFF-0011-2233-445566778899"
        self.assertEqual(
            pc.credential_id_from_bitwarden(text).hex(), "aabbccddeeff00112233445566778899"
        )


class Base64Url(unittest.TestCase):
    # If this fails: output contains '+', '/' or '=' which Bitwarden's
    # stringToArray would treat as a different value or reject.
    def test_encoding_is_unpadded_urlsafe_for_every_length(self):
        for length in range(0, 70):
            data = bytes((i * 37 + 250) % 256 for i in range(length))
            text = pc.b64url_encode(data)
            self.assertNotRegex(text, r"[+/=]")
            self.assertEqual(pc.b64url_decode(text), data)

    # If this fails: a length of 1 mod 4 (impossible base64) decodes to junk.
    def test_rejects_impossible_length_and_bad_alphabet(self):
        for bad in ("A", "AAAAA", "ab$d", "ab+d"):
            with self.subTest(bad=bad):
                with self.assertRaises(pc.ConversionError):
                    pc.b64url_decode(bad)


class PasslessRecord(unittest.TestCase):
    # If this fails: passless writes int arrays; a reader that only handled
    # byte strings would drop every credential passless itself created.
    def test_reads_int_array_byte_fields_as_passless_writes_them(self):
        record = a_passless_record()
        for key in ("id", "private_key"):
            record[key] = list(record[key])
        record["user"] = {**record["user"], "id": list(record["user"]["id"])}
        self.assertEqual(pc.passkey_from_passless(record).credential_id, bytes(record["id"]))

    # If this fails: passless and Bitwarden disagree on identity after a push+pull.
    def test_passless_to_neutral_and_back_is_lossless(self):
        passkey = a_passkey()
        self.assertEqual(
            pc.passkey_from_passless(pc.passless_from_passkey(passkey)), passkey
        )

    # If this fails: the record we write cannot be parsed by passless. This goes
    # through CBOR encode/decode to catch type problems (e.g. str vs bytes, null).
    def test_record_survives_cbor_encoding(self):
        passkey = a_passkey()
        wire = pc.cbor_encode(pc.passless_from_passkey(passkey))
        self.assertEqual(pc.passkey_from_passless(pc.cbor_decode(wire)), passkey)

    # If this fails: imported credentials would report BE=0 after Bitwarden
    # registered them as BE=1, and strict relying parties reject that.
    def test_imported_credentials_stay_backed_up(self):
        self.assertEqual(pc.passless_from_passkey(a_passkey())["backup_state"], "backedUp")

    # If this fails: an Ed25519 or RSA passkey is pushed to Bitwarden with a
    # P-256 label and fails at sign time.
    def test_refuses_non_es256_algorithms(self):
        for alg in (-8, -257, 0):
            with self.subTest(alg=alg):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_passless(a_passless_record(alg=alg))

    # If this fails: a TPM-sealed key blob is exported as if it were a scalar.
    def test_refuses_hardware_backed_keys(self):
        with self.assertRaises(pc.ConversionError):
            pc.passkey_from_passless(a_passless_record(key_provider=[1, 2, 3]))

    # If this fails: a truncated record is converted with defaults instead of failing.
    def test_missing_fields_fail_loudly(self):
        for field in ("id", "rp", "user", "sign_count", "alg", "private_key", "created", "discoverable"):
            record = a_passless_record()
            del record[field]
            with self.subTest(field=field):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_passless(record)

    # If this fails: bad byte fields (strings, out-of-range ints) are accepted.
    def test_rejects_non_byte_values(self):
        for bad in ("text", [256], [-1], 5, [1.5]):
            with self.subTest(bad=bad):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_passless(a_passless_record(id=bad))


class BitwardenEntry(unittest.TestCase):
    # If this fails: a vault round trip changes a passkey.
    def test_neutral_to_bitwarden_and_back_is_lossless(self):
        passkey = a_passkey()
        self.assertEqual(
            pc.passkey_from_bitwarden(pc.passkey_to_bitwarden(passkey)), passkey
        )

    # If this fails: the JSON `bw edit` receives has the wrong shape or types
    # (Bitwarden requires every value as a string and fixed algorithm labels).
    def test_entry_has_bitwarden_shape(self):
        entry = pc.passkey_to_bitwarden(a_passkey(sign_count=42, discoverable=False))
        self.assertEqual(entry["keyType"], "public-key")
        self.assertEqual(entry["keyAlgorithm"], "ECDSA")
        self.assertEqual(entry["keyCurve"], "P-256")
        self.assertEqual(entry["counter"], "42")
        self.assertEqual(entry["discoverable"], "false")
        self.assertRegex(entry["creationDate"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.000Z$")
        for value in entry.values():
            self.assertIsInstance(value, (str, type(None)))

    # If this fails: nullable fields (rpName, userName, displayName) crash the
    # conversion for sites that omit them, which is common.
    def test_optional_names_may_be_absent(self):
        passkey = a_passkey(rp_name=None, user_name=None, user_display_name=None)
        self.assertEqual(
            pc.passkey_from_bitwarden(pc.passkey_to_bitwarden(passkey)), passkey
        )

    # If this fails: a Bitwarden entry with a different algorithm label is imported.
    def test_refuses_foreign_algorithm_labels(self):
        for field, bad in (("keyType", "other"), ("keyAlgorithm", "RSA"), ("keyCurve", "P-384")):
            entry = pc.passkey_to_bitwarden(a_passkey())
            entry[field] = bad
            with self.subTest(field=field):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_bitwarden(entry)

    # If this fails: counters outside u32 overflow passless's u32 sign_count.
    def test_counter_bounds(self):
        entry = pc.passkey_to_bitwarden(a_passkey())
        for ok in ("0", "4294967295"):
            entry["counter"] = ok
            self.assertEqual(pc.passkey_from_bitwarden(entry).sign_count, int(ok))
        for bad in ("-1", "4294967296", "abc", "1.5", ""):
            entry["counter"] = bad
            with self.subTest(bad=bad):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_bitwarden(entry)

    # If this fails: Bitwarden's "true"/"True"/"false" spellings mis-set discoverability.
    def test_discoverable_parsing(self):
        entry = pc.passkey_to_bitwarden(a_passkey())
        for text, expected in (("true", True), ("True", True), ("false", False), ("", False)):
            entry["discoverable"] = text
            with self.subTest(text=text):
                self.assertEqual(pc.passkey_from_bitwarden(entry).discoverable, expected)

    # If this fails: a timezone-less date is guessed as local time.
    def test_creation_date_requires_timezone(self):
        entry = pc.passkey_to_bitwarden(a_passkey())
        entry["creationDate"] = "2024-01-01T00:00:00"
        with self.assertRaises(pc.ConversionError):
            pc.passkey_from_bitwarden(entry)

    # If this fails: a Bitwarden date with real milliseconds, as the web client
    # writes it, is rejected.
    def test_creation_date_accepts_milliseconds(self):
        entry = pc.passkey_to_bitwarden(a_passkey(created=1_700_000_000))
        entry["creationDate"] = "2023-11-14T22:13:20.123Z"
        self.assertEqual(pc.passkey_from_bitwarden(entry).created, 1_700_000_000)

    # If this fails: a half-filled entry imports with defaults instead of failing.
    def test_missing_required_fields_fail(self):
        for field in ("credentialId", "keyValue", "rpId", "userHandle", "counter", "creationDate"):
            entry = pc.passkey_to_bitwarden(a_passkey())
            del entry[field]
            with self.subTest(field=field):
                with self.assertRaises(pc.ConversionError):
                    pc.passkey_from_bitwarden(entry)


class Cbor(unittest.TestCase):
    # If this fails: our encoder disagrees with the standard, so passless's
    # cbor4ii reader would see different values than we meant to write.
    # Vectors are RFC 8949 Appendix A, not produced by this code.
    def test_matches_rfc8949_appendix_a_vectors(self):
        vectors = [
            (0, "00"), (23, "17"), (24, "1818"), (255, "18ff"), (256, "190100"),
            (65535, "19ffff"), (65536, "1a00010000"), (4294967295, "1affffffff"),
            (4294967296, "1b0000000100000000"), (-1, "20"), (-10, "29"), (-100, "3863"),
            (-1000, "3903e7"), (False, "f4"), (True, "f5"), (None, "f6"), (b"", "40"),
            (b"\x01\x02\x03\x04", "4401020304"), ("", "60"), ("IETF", "6449455446"),
            ("\u00fc", "62c3bc"), ({}, "a0"), ({"a": 1}, "a1616101"),
        ]
        for value, hexed in vectors:
            with self.subTest(hexed=hexed):
                self.assertEqual(pc.cbor_encode(value).hex(), hexed)
                decoded = pc.cbor_decode(bytes.fromhex(hexed))
                self.assertEqual(decoded, value)
                self.assertIs(type(decoded), type(value))  # True must not come back as 1

    # If this fails: Option::None fields (rp.name etc.) are dropped or mangled
    # and passless cannot read the record.
    def test_null_values_are_preserved_inside_maps(self):
        wire = pc.cbor_encode({"name": None, "id": b"\x01"})
        self.assertEqual(pc.cbor_decode(wire), {"name": None, "id": b"\x01"})

    # If this fails: truncated or trailing data decodes silently, so a
    # half-written credential file is treated as valid.
    def test_rejects_truncated_trailing_and_unsupported_input(self):
        good = pc.cbor_encode({"k": b"\x01\x02\x03"})
        for bad in (good[:-1], good + b"\x00", b"", b"\x5f", b"\xf9\x3c\x00", b"\xc0\x60"):
            with self.subTest(bad=bad.hex()):
                with self.assertRaises(pc.ConversionError):
                    pc.cbor_decode(bad)

    # If this fails: non-text map keys, which passless never writes, are accepted.
    def test_rejects_non_text_map_keys(self):
        with self.assertRaises(pc.ConversionError):
            pc.cbor_decode(bytes.fromhex("a10101"))

    # If this fails: ints at width boundaries encode in the wrong header size.
    def test_integer_width_boundaries_roundtrip(self):
        for n in (0, 23, 24, 255, 256, 65535, 65536, 2**32 - 1, 2**32, 2**64 - 1, -1, -24, -25, -256, -257, -(2**63)):
            with self.subTest(n=n):
                self.assertEqual(pc.cbor_decode(pc.cbor_encode(n)), n)


if __name__ == "__main__":
    unittest.main()
