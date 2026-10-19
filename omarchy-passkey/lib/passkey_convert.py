"""Convert one passkey between passless's on-disk record and Bitwarden's fido2Credential.

Pure functions only: no I/O, no subprocesses, no clock. That keeps the one piece
of this feature that can silently corrupt a passkey fully unit-testable.

Two formats meet here.

passless record (decrypted `<rpId>/<hex credId>.gpg`), a CBOR map:
    id: bytes, rp: {id, name}, user: {id, name, display_name}, sign_count: int,
    alg: int (COSE, -7 = ES256), private_key: 32-byte raw P-256 scalar,
    created: int (unix seconds), discoverable: bool, backup_state: str,
    key_provider/key_format_version: only for non-software keys.

Bitwarden `login.fido2Credentials[i]` (all values are strings, as `bw` emits them):
    credentialId   UUID string when the id is 16 bytes, else "b64." + base64url
    keyType        always "public-key"
    keyAlgorithm   always "ECDSA"
    keyCurve       always "P-256"
    keyValue       base64url, no padding, of the PKCS#8 DER private key
    rpId, rpName, userName, userDisplayName   plain strings
    userHandle     base64url, no padding
    counter        decimal string
    discoverable   "true" / "false"
    creationDate   ISO-8601 UTC

Source of truth for the Bitwarden side:
bitwarden/clients libs/common/src/platform/services/fido2/{fido2-authenticator.service,
credential-id-utils,fido2-utils}.ts.
"""

from __future__ import annotations

import base64
import datetime as dt
import re
import uuid
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

COSE_ES256 = -7
P256_SCALAR_LEN = 32

# Bitwarden's own authenticator reports BE=1 BS=1 for every passkey because the
# vault syncs it. A relying party that saw BE=1 at registration rejects a later
# assertion with BE=0, so imported credentials must keep reporting backed-up.
PASSLESS_BACKED_UP = "backedUp"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_B64_PREFIX = "b64."
_B64URL_RE = re.compile(r"[A-Za-z0-9_-]*")


class ConversionError(ValueError):
    """A credential cannot be represented in the other format."""


@dataclass(frozen=True)
class Passkey:
    """Everything both formats agree on, in native types. The neutral form."""

    credential_id: bytes
    rp_id: str
    rp_name: str | None
    user_handle: bytes
    user_name: str | None
    user_display_name: str | None
    sign_count: int
    discoverable: bool
    created: int  # unix seconds
    private_scalar: bytes  # raw 32-byte P-256 scalar


# --- base64url (no padding), exactly Bitwarden's Fido2Utils.arrayToString ---


def b64url_encode(data: bytes) -> str:
    """Encode bytes as unpadded base64url."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    """Decode unpadded base64url, the only form Bitwarden writes.

    Raises ConversionError on a length that cannot be valid base64, or on any
    character outside [A-Za-z0-9_-] (so '+', '/' and '=' are rejected).
    """
    if len(text) % 4 == 1:
        raise ConversionError(f"illegal base64url length: {len(text)}")
    if not _B64URL_RE.fullmatch(text):
        raise ConversionError("illegal base64url string: characters outside [A-Za-z0-9_-]")
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --- credential id ---


def credential_id_to_bitwarden(raw: bytes) -> str:
    """16-byte ids become canonical UUID strings; anything else gets a b64. prefix.

    This is the inverse of Bitwarden's parseCredentialId. Bitwarden mints UUIDs,
    so a credential made by Bitwarden round-trips to the same string; passless
    mints 32-byte ids, which take the b64. form.
    """
    if not raw:
        raise ConversionError("empty credential id")
    if len(raw) == 16:
        return str(uuid.UUID(bytes=raw))
    return _B64_PREFIX + b64url_encode(raw)


def credential_id_from_bitwarden(text: str) -> bytes:
    """Inverse of credential_id_to_bitwarden. Accepts both Bitwarden forms."""
    if text.startswith(_B64_PREFIX):
        raw = b64url_decode(text[len(_B64_PREFIX) :])
    elif _UUID_RE.match(text):
        raw = uuid.UUID(text).bytes
    else:
        raise ConversionError(f"unrecognised credentialId: {text!r}")
    if not raw:
        raise ConversionError("empty credential id")
    return raw


# --- private key ---


def scalar_to_pkcs8(scalar: bytes) -> bytes:
    """Wrap a raw 32-byte P-256 scalar as PKCS#8 DER, as WebCrypto exports it."""
    if len(scalar) != P256_SCALAR_LEN:
        raise ConversionError(f"P-256 scalar must be 32 bytes, got {len(scalar)}")
    value = int.from_bytes(scalar, "big")
    try:
        key = ec.derive_private_key(value, ec.SECP256R1())
    except ValueError as exc:
        raise ConversionError(f"not a valid P-256 scalar: {exc}") from exc
    return key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def pkcs8_to_scalar(der: bytes) -> bytes:
    """Unwrap PKCS#8 DER to a raw 32-byte P-256 scalar. Rejects any other curve."""
    try:
        key = serialization.load_der_private_key(der, password=None)
    except (ValueError, TypeError) as exc:
        raise ConversionError(f"not a PKCS#8 private key: {exc}") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise ConversionError("private key is not P-256")
    return key.private_numbers().private_value.to_bytes(P256_SCALAR_LEN, "big")


# --- passless record <-> neutral ---


def _require(record: dict[str, Any], key: str) -> Any:
    if key not in record or record[key] is None:
        raise ConversionError(f"passless record is missing {key!r}")
    return record[key]


def _as_bytes(value: Any, what: str) -> bytes:
    """passless writes byte fields as int arrays but also accepts byte strings."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, list) and all(isinstance(b, int) and 0 <= b < 256 for b in value):
        return bytes(value)
    raise ConversionError(f"{what} is neither bytes nor a byte array")


def passkey_from_passless(record: dict[str, Any]) -> Passkey:
    """Read a decoded passless record.

    Raises ConversionError for anything Bitwarden cannot hold: a non-ES256
    algorithm, or a key that is not a software key (key_provider set).
    """
    alg = _require(record, "alg")
    if alg != COSE_ES256:
        raise ConversionError(f"only ES256 (-7) passkeys fit Bitwarden, got alg {alg}")
    if record.get("key_provider") is not None:
        raise ConversionError("hardware-backed key cannot be exported to Bitwarden")
    rp = _require(record, "rp")
    user = _require(record, "user")
    return Passkey(
        credential_id=_as_bytes(_require(record, "id"), "id"),
        rp_id=_require(rp, "id"),
        rp_name=rp.get("name"),
        user_handle=_as_bytes(_require(user, "id"), "user.id"),
        user_name=user.get("name"),
        user_display_name=user.get("display_name"),
        sign_count=_require(record, "sign_count"),
        discoverable=bool(_require(record, "discoverable")),
        created=_require(record, "created"),
        private_scalar=_as_bytes(_require(record, "private_key"), "private_key"),
    )


def passless_from_passkey(passkey: Passkey) -> dict[str, Any]:
    """Build a record passless will accept. Byte fields use CBOR byte strings.

    passless's reader takes byte strings as well as its historical int arrays,
    and `bytes` encodes as a byte string under fido2.cbor.
    """
    if len(passkey.private_scalar) != P256_SCALAR_LEN:
        raise ConversionError("private scalar must be 32 bytes")
    return {
        "id": passkey.credential_id,
        "rp": {"id": passkey.rp_id, "name": passkey.rp_name},
        "user": {
            "id": passkey.user_handle,
            "name": passkey.user_name,
            "display_name": passkey.user_display_name,
        },
        "sign_count": passkey.sign_count,
        "alg": COSE_ES256,
        "private_key": passkey.private_scalar,
        "created": passkey.created,
        "discoverable": passkey.discoverable,
        "backup_state": PASSLESS_BACKED_UP,
        "extensions": {"cred_protect": None, "hmac_secret": None},
    }


# --- neutral <-> Bitwarden ---


def _iso(seconds: int) -> str:
    stamp = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _from_iso(text: str) -> int:
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConversionError(f"bad creationDate {text!r}") from exc
    if parsed.tzinfo is None:
        raise ConversionError(f"creationDate {text!r} has no timezone")
    return int(parsed.timestamp())


def passkey_to_bitwarden(passkey: Passkey) -> dict[str, str | None]:
    """Render the Bitwarden `fido2Credentials` entry for this passkey."""
    return {
        "credentialId": credential_id_to_bitwarden(passkey.credential_id),
        "keyType": "public-key",
        "keyAlgorithm": "ECDSA",
        "keyCurve": "P-256",
        "keyValue": b64url_encode(scalar_to_pkcs8(passkey.private_scalar)),
        "rpId": passkey.rp_id,
        "rpName": passkey.rp_name,
        "userHandle": b64url_encode(passkey.user_handle),
        "userName": passkey.user_name,
        "userDisplayName": passkey.user_display_name,
        "counter": str(passkey.sign_count),
        "discoverable": "true" if passkey.discoverable else "false",
        "creationDate": _iso(passkey.created),
    }


def passkey_from_bitwarden(entry: dict[str, Any]) -> Passkey:
    """Read a Bitwarden `fido2Credentials` entry.

    Raises ConversionError for a non-ES256/P-256 credential or malformed field.
    """
    for field, expected in (
        ("keyType", "public-key"),
        ("keyAlgorithm", "ECDSA"),
        ("keyCurve", "P-256"),
    ):
        if entry.get(field) != expected:
            raise ConversionError(f"{field} is {entry.get(field)!r}, need {expected!r}")
    for field in ("credentialId", "keyValue", "rpId", "userHandle", "counter", "creationDate"):
        if not entry.get(field) and entry.get(field) != 0:
            raise ConversionError(f"Bitwarden entry is missing {field!r}")
    try:
        counter = int(entry["counter"])
    except ValueError as exc:
        raise ConversionError(f"bad counter {entry['counter']!r}") from exc
    if counter < 0 or counter > 0xFFFFFFFF:
        raise ConversionError(f"counter {counter} does not fit in 32 bits")
    return Passkey(
        credential_id=credential_id_from_bitwarden(entry["credentialId"]),
        rp_id=entry["rpId"],
        rp_name=entry.get("rpName"),
        user_handle=b64url_decode(entry["userHandle"]),
        user_name=entry.get("userName"),
        user_display_name=entry.get("userDisplayName"),
        sign_count=counter,
        discoverable=str(entry.get("discoverable")).lower() == "true",
        created=_from_iso(entry["creationDate"]),
        private_scalar=pkcs8_to_scalar(b64url_decode(entry["keyValue"])),
    )


# --- CBOR for passless records ---
#
# fido2.cbor is CTAP2-canonical and cannot express null, but passless's serde
# reader needs `null` for `Option::None` fields. The record shape is small and
# fixed (maps with text keys; int, bytes, text, bool, null), so it is encoded
# here rather than pulling in a dependency. Maps keep insertion order: passless
# reads by key name, not position.


def cbor_encode(value: Any) -> bytes:
    """Encode None, bool, int, bytes, str, dict[str, ...] to CBOR."""
    if value is None:
        return b"\xf6"
    if value is True:
        return b"\xf5"
    if value is False:
        return b"\xf4"
    if isinstance(value, int):
        return _head(0, value) if value >= 0 else _head(1, -1 - value)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(value, dict):
        out = _head(5, len(value))
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConversionError(f"CBOR map keys must be text, got {type(key).__name__}")
            out += cbor_encode(key) + cbor_encode(item)
        return out
    raise ConversionError(f"cannot CBOR-encode {type(value).__name__}")


def _head(major: int, argument: int) -> bytes:
    if argument < 24:
        return bytes([major << 5 | argument])
    for extra, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
        if argument < 1 << (8 * size):
            return bytes([major << 5 | extra]) + argument.to_bytes(size, "big")
    raise ConversionError("integer too large for CBOR")


def cbor_decode(data: bytes) -> Any:
    """Decode what passless writes: ints, bytes, text, bool, null, arrays, maps.

    Raises ConversionError on trailing bytes, truncation or unsupported types
    (floats, tags, indefinite lengths).
    """
    value, end = _decode_at(data, 0)
    if end != len(data):
        raise ConversionError(f"{len(data) - end} trailing bytes after CBOR value")
    return value


def _decode_at(data: bytes, pos: int) -> tuple[Any, int]:
    if pos >= len(data):
        raise ConversionError("truncated CBOR")
    initial = data[pos]
    major, info = initial >> 5, initial & 0x1F
    pos += 1
    if major == 7:
        if info == 20:
            return False, pos
        if info == 21:
            return True, pos
        if info == 22:
            return None, pos
        raise ConversionError(f"unsupported CBOR simple value {info}")
    if info < 24:
        argument = info
    elif info in (24, 25, 26, 27):
        size = 1 << (info - 24)
        if pos + size > len(data):
            raise ConversionError("truncated CBOR")
        argument = int.from_bytes(data[pos : pos + size], "big")
        pos += size
    else:
        raise ConversionError("indefinite-length CBOR is not supported")
    if major == 0:
        return argument, pos
    if major == 1:
        return -1 - argument, pos
    if major in (2, 3):
        if pos + argument > len(data):
            raise ConversionError("truncated CBOR")
        chunk = data[pos : pos + argument]
        try:
            return (chunk if major == 2 else chunk.decode("utf-8")), pos + argument
        except UnicodeDecodeError as exc:
            raise ConversionError("invalid UTF-8 in CBOR text") from exc
    if major == 4:
        items = []
        for _ in range(argument):
            item, pos = _decode_at(data, pos)
            items.append(item)
        return items, pos
    if major == 5:
        mapping: dict[Any, Any] = {}
        for _ in range(argument):
            key, pos = _decode_at(data, pos)
            if not isinstance(key, str):
                raise ConversionError("CBOR map keys must be text")
            mapping[key], pos = _decode_at(data, pos)
        return mapping, pos
    raise ConversionError(f"unsupported CBOR major type {major}")
