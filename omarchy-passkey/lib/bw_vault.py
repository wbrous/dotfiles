"""Read and write passkeys in a Bitwarden vault through a local `bw serve`.

`bw serve` keeps the unlocked session itself, so this module never holds a
session key or master password beyond the one `unlock` call.

Every vault item that carries a passkey is a Login. We tag items we create with
a custom field so we can find them again, and we never modify, move or delete
an item we did not create, except to add the passkey to a Login the user already
has for that site when they ask for that (not done here; `push` always creates).

Response envelope from `bw serve`: {"success": bool, "data": ..., "message": ...}.
"""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from passkey_convert import ConversionError, Passkey, passkey_from_bitwarden, passkey_to_bitwarden

# Marks items this tool created, so `pull` ignores nothing and `push` never
# duplicates. The value is the credential id, which is unique per passkey.
OWNER_FIELD = "omarchy-passkey"
LOGIN_TYPE = 1


class VaultError(RuntimeError):
    """The vault could not be read or written."""


class VaultLocked(VaultError):
    """The vault is locked or not logged in; the user must unlock it."""


Transport = Callable[[str, str, "dict[str, Any] | None"], "dict[str, Any]"]


def http_transport(base_url: str, timeout: float = 30.0) -> Transport:
    """Real HTTP transport. Raises VaultError on any network failure.

    `bw serve` reports vault-level errors (locked, wrong password) as HTTP 400
    with the usual {"success": false, "message": ...} envelope in the body, so a
    4xx/5xx whose body is that envelope is returned like any other reply and
    interpreted by Vault. Any other error body (a proxy page, a crash) is a
    VaultError carrying the status code.

    A refused connection means `bw serve` is not running; that is a VaultError,
    never an empty vault, so a down server cannot look like "no passkeys".
    """

    def call(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            with exc:  # HTTPError owns the socket; close it once the body is read
                raw = exc.read()
            envelope = _envelope_or_none(raw)
            if envelope is None:
                raise VaultError(f"{method} {path}: HTTP {exc.code}") from exc
            return envelope
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VaultError(f"{method} {path}: {exc}") from exc
        envelope = _envelope_or_none(raw)
        if envelope is None:
            raise VaultError(f"{method} {path}: response is not a bw serve envelope")
        return envelope

    return call


# bw serve's DNS-rebinding guard only admits Hosts of the form localhost:<port>,
# 127.0.0.1:<port> or [::1]:<port>, even over a Unix socket. The port is not used.
_UNIX_HOST_HEADER = "localhost:8087"


class _UnixConnection(http.client.HTTPConnection):
    """HTTP over a Unix socket; urllib cannot do this."""

    def __init__(self, path: str, timeout: float):
        super().__init__(_UNIX_HOST_HEADER, timeout=timeout)
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def unix_transport(socket_path: str, timeout: float = 30.0) -> Transport:
    """Transport to a `bw serve --hostname unix://<socket_path>`.

    Preferred over TCP: only the socket's owner (and root) can connect, and the
    owner can be verified, whereas any local process can bind or reach a TCP port.
    Replies are interpreted exactly as in http_transport (HTTP 400 + envelope is
    a vault-level error, anything else non-envelope is a VaultError).
    """

    def call(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "Content-Length": str(len(data))} if data else {}
        connection = _UnixConnection(socket_path, timeout)
        try:
            connection.request(method, path, body=data, headers=headers)
            raw = connection.getresponse().read()
        except (OSError, http.client.HTTPException) as exc:
            raise VaultError(f"{method} {path}: {exc}") from exc
        finally:
            connection.close()
        envelope = _envelope_or_none(raw)
        if envelope is None:
            raise VaultError(f"{method} {path}: response is not a bw serve envelope")
        return envelope

    return call


def _envelope_or_none(raw: bytes) -> dict[str, Any] | None:
    """The parsed reply if it is a JSON object with a boolean `success`, else None."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("success"), bool):
        return parsed
    return None


class Vault:
    """Passkey operations on a vault reached through `transport`."""

    def __init__(self, transport: Transport):
        self._call = transport

    def _data(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        reply = self._call(method, path, body)
        if reply.get("success") is not True:
            message = str(reply.get("message", "unknown error"))
            if "locked" in message.lower() or "not logged in" in message.lower():
                raise VaultLocked(message)
            raise VaultError(f"{method} {path}: {message}")
        return reply.get("data")

    def unlock(self, password: str) -> None:
        """Unlock the vault held by `bw serve`. Raises VaultError on a wrong password."""
        self._data("POST", "/unlock", {"password": password})

    def is_unlocked(self) -> bool:
        """True iff `bw serve` reports an unlocked vault."""
        status = self._data("GET", "/status")
        return status["template"]["status"] == "unlocked"

    def sync(self) -> None:
        """Pull the latest vault from the Bitwarden server."""
        self._data("POST", "/sync")

    def list_passkeys(self) -> list[tuple[str, Passkey]]:
        """Every (item id, passkey) in the vault, from any Login, ours or not.

        Credentials Bitwarden holds that we cannot represent (non-P-256) are
        skipped here and counted by `skipped_count`, not raised, because they
        are the user's valid data that simply does not apply to this tool.
        """
        self.skipped: list[str] = []
        found: list[tuple[str, Passkey]] = []
        items = self._data("GET", "/list/object/items")["data"]
        for item in items:
            if item.get("type") != LOGIN_TYPE:
                continue
            for entry in (item.get("login") or {}).get("fido2Credentials") or []:
                try:
                    found.append((item["id"], passkey_from_bitwarden(entry)))
                except ConversionError as exc:
                    self.skipped.append(f"{item.get('name')}: {exc}")
        return found

    def create_passkey_item(self, passkey: Passkey) -> str:
        """Create a new Login holding exactly this passkey; return its item id."""
        entry = passkey_to_bitwarden(passkey)
        item = {
            "type": LOGIN_TYPE,
            "name": passkey.rp_name or passkey.rp_id,
            "notes": None,
            "favorite": False,
            "reprompt": 0,
            "fields": [{"name": OWNER_FIELD, "value": entry["credentialId"], "type": 0}],
            "login": {
                "username": passkey.user_name,
                "password": None,
                "totp": None,
                "uris": [{"uri": f"https://{passkey.rp_id}", "match": None}],
                "fido2Credentials": [entry],
            },
        }
        return self._data("POST", "/object/item", item)["id"]

    def set_counter(self, item_id: str, passkey: Passkey) -> None:
        """Write a new signature counter onto the credential inside an item.

        Only the matching credential's `counter` changes; every other field of
        the item, including other passkeys, is sent back exactly as read.
        """
        item = self._data("GET", f"/object/item/{item_id}")
        wanted = passkey_to_bitwarden(passkey)["credentialId"]
        for entry in item["login"]["fido2Credentials"]:
            if entry["credentialId"] == wanted:
                entry["counter"] = str(passkey.sign_count)
                self._data("PUT", f"/object/item/{item_id}", item)
                return
        raise VaultError(f"item {item_id} does not contain credential {wanted}")
