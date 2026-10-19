import copy
import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import bw_vault as bv
import passkey_convert as pc
from test_passkey_convert import a_passkey


def ok(data):
    return {"success": True, "data": data}


class FakeServer:
    """Stands in for `bw serve`, replying with the envelopes it really sends.

    Reply shapes were recorded from a live `bw serve` (locked vault):
    /status -> data.template.status, locked -> {"success": false, "message": "Vault is locked."}.
    """

    def __init__(self, items=None, locked=False):
        self.items = {i["id"]: i for i in (items or [])}
        self.locked = locked
        self.calls = []

    def __call__(self, method, path, body):
        self.calls.append((method, path))
        if path == "/status":
            return ok({"object": "template", "template": {"status": "locked" if self.locked else "unlocked"}})
        if self.locked:
            return {"success": False, "message": "Vault is locked."}
        if (method, path) == ("GET", "/list/object/items"):
            return ok({"object": "list", "data": list(self.items.values())})
        if (method, path) == ("POST", "/object/item"):
            item = copy.deepcopy(body)
            item["id"] = f"item-{len(self.items) + 1}"
            self.items[item["id"]] = item
            return ok(item)
        if path.startswith("/object/item/"):
            item_id = path.rsplit("/", 1)[1]
            if method == "GET":
                return ok(copy.deepcopy(self.items[item_id]))
            if method == "PUT":
                self.items[item_id] = copy.deepcopy(body)
                return ok(body)
        raise AssertionError(f"unexpected call {method} {path}")


def login_with(passkey, item_id="existing-1", name="Example"):
    return {
        "id": item_id, "type": 1, "name": name,
        "login": {"fido2Credentials": [pc.passkey_to_bitwarden(passkey)]},
    }


class ListPasskeys(unittest.TestCase):
    # If this fails: passkeys already in the vault are not found, so a sync
    # would push duplicates of every one.
    def test_finds_passkeys_on_logins(self):
        a, b = a_passkey(), a_passkey()
        vault = bv.Vault(FakeServer([login_with(a, "1"), login_with(b, "2")]))
        self.assertEqual({p for _, p in vault.list_passkeys()}, {a, b})

    # If this fails: non-Login items (cards, notes) or logins with no passkey
    # crash the listing for the whole vault.
    def test_ignores_items_without_passkeys(self):
        items = [
            {"id": "n", "type": 2, "name": "note"},
            {"id": "l", "type": 1, "name": "plain", "login": {"username": "u"}},
            {"id": "x", "type": 1, "name": "nologin"},
            {"id": "y", "type": 1, "name": "null", "login": {"fido2Credentials": None}},
        ]
        self.assertEqual(bv.Vault(FakeServer(items)).list_passkeys(), [])

    # If this fails: one non-P-256 passkey in the user's vault makes the entire
    # sync fail, blocking every other passkey. It must be skipped and reported.
    def test_unrepresentable_credentials_are_skipped_and_reported(self):
        good = a_passkey()
        foreign = pc.passkey_to_bitwarden(a_passkey())
        foreign["keyCurve"] = "P-384"
        items = [
            login_with(good, "1"),
            {"id": "2", "type": 1, "name": "Weird", "login": {"fido2Credentials": [foreign]}},
        ]
        vault = bv.Vault(FakeServer(items))
        self.assertEqual([p for _, p in vault.list_passkeys()], [good])
        self.assertEqual(len(vault.skipped), 1)
        self.assertIn("Weird", vault.skipped[0])

    # If this fails: a locked vault reads as "no passkeys", and a sync would
    # then try to push everything or conclude the user deleted it all.
    def test_locked_vault_raises_instead_of_returning_empty(self):
        with self.assertRaises(bv.VaultLocked):
            bv.Vault(FakeServer(locked=True)).list_passkeys()


class CreateItem(unittest.TestCase):
    # If this fails: a pushed passkey is not readable back from the vault, so
    # the next sync pushes it again (duplicate on every run).
    def test_created_item_is_found_by_list(self):
        a = a_passkey()
        server = FakeServer()
        vault = bv.Vault(server)
        item_id = vault.create_passkey_item(a)
        self.assertEqual(vault.list_passkeys(), [(item_id, a)])

    # If this fails: the item is created as a type Bitwarden clients will not
    # offer for sign-in, or without the site URL they match on.
    def test_item_is_a_login_for_the_site(self):
        a = a_passkey(rp_id="site.example", rp_name="Site")
        server = FakeServer()
        bv.Vault(server).create_passkey_item(a)
        (item,) = server.items.values()
        self.assertEqual(item["type"], 1)
        self.assertEqual(item["name"], "Site")
        self.assertEqual(item["login"]["uris"][0]["uri"], "https://site.example")

    # If this fails: an RP with no display name produces an item with a null
    # name, which Bitwarden rejects.
    def test_name_falls_back_to_rp_id(self):
        server = FakeServer()
        bv.Vault(server).create_passkey_item(a_passkey(rp_id="bare.example", rp_name=None))
        self.assertEqual(next(iter(server.items.values()))["name"], "bare.example")


class SetCounter(unittest.TestCase):
    # If this fails: updating the counter clobbers other fields of the user's
    # item (password, notes, other passkeys), i.e. data loss in a real vault.
    def test_only_the_counter_changes(self):
        a, other = a_passkey(sign_count=1), a_passkey(sign_count=4)
        item = login_with(a)
        item["login"]["password"] = "hunter2"
        item["notes"] = "keep me"
        item["login"]["fido2Credentials"].append(pc.passkey_to_bitwarden(other))
        server = FakeServer([item])
        before = copy.deepcopy(server.items["existing-1"])
        bv.Vault(server).set_counter("existing-1", dataclasses.replace(a, sign_count=9))
        after = server.items["existing-1"]
        self.assertEqual(after["login"]["fido2Credentials"][0]["counter"], "9")
        after["login"]["fido2Credentials"][0]["counter"] = before["login"]["fido2Credentials"][0]["counter"]
        self.assertEqual(after, before)

    # If this fails: a counter is written to the wrong credential or silently
    # dropped when the item does not hold it.
    def test_unknown_credential_is_an_error(self):
        server = FakeServer([login_with(a_passkey())])
        with self.assertRaises(bv.VaultError):
            bv.Vault(server).set_counter("existing-1", a_passkey())


class Envelope(unittest.TestCase):
    # If this fails: a wrong master password is reported as "locked" and the
    # caller loops prompting forever instead of showing the real error.
    def test_error_that_is_not_locked_is_a_plain_vault_error(self):
        def transport(method, path, body):
            return {"success": False, "message": "Cryptography error, The decryption operation failed"}
        with self.assertRaises(bv.VaultError) as caught:
            bv.Vault(transport).unlock("x")
        self.assertNotIsInstance(caught.exception, bv.VaultLocked)

    # If this fails: both "not logged in" and "locked" are not recognised as
    # needing the user, so the daemon retries instead of prompting.
    def test_not_logged_in_is_treated_as_locked(self):
        def transport(method, path, body):
            return {"success": False, "message": "You are not logged in."}
        with self.assertRaises(bv.VaultLocked):
            bv.Vault(transport).sync()

    # If this fails: is_unlocked misreads the real /status shape.
    def test_is_unlocked_reads_status(self):
        self.assertTrue(bv.Vault(FakeServer()).is_unlocked())
        self.assertFalse(bv.Vault(FakeServer(locked=True)).is_unlocked())


class RealBwServeStatusCodes(unittest.TestCase):
    """`bw serve` answers errors with HTTP 400 and the JSON envelope in the body
    (observed: locked vault and wrong password both return 400). A fake that
    only returns 200 hides this, so this runs the real transport against a real
    local HTTP server that behaves the same way."""

    def serve(self, status, body):
        import http.server, threading, json as _json

        class Handler(http.server.BaseHTTPRequestHandler):
            def respond(self):
                payload = _json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = respond

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f"http://127.0.0.1:{server.server_address[1]}"

    # If this fails: a locked vault (HTTP 400) is reported as a generic error,
    # so nothing prompts the user to unlock and passkeys silently never sync.
    def test_http_400_locked_is_vault_locked(self):
        url = self.serve(400, {"success": False, "message": "Vault is locked."})
        with self.assertRaises(bv.VaultLocked):
            bv.Vault(bv.http_transport(url)).list_passkeys()

    # If this fails: the server's real error text is dropped and the user only
    # sees "HTTP 400", which cannot be acted on.
    def test_http_400_message_is_preserved(self):
        url = self.serve(400, {"success": False, "message": "Cryptography error, The decryption operation failed"})
        with self.assertRaises(bv.VaultError) as caught:
            bv.Vault(bv.http_transport(url)).sync()
        self.assertIn("decryption operation failed", str(caught.exception))
        self.assertNotIsInstance(caught.exception, bv.VaultLocked)

    # If this fails: a 5xx or non-JSON body (proxy error page) is mistaken for a
    # vault answer instead of failing loudly.
    def test_non_envelope_error_body_is_a_vault_error(self):
        import http.server, threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(502)
                self.send_header("Content-Length", "9")
                self.end_headers()
                self.wfile.write(b"bad gatew")

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        with self.assertRaises(bv.VaultError):
            bv.Vault(bv.http_transport(f"http://127.0.0.1:{server.server_address[1]}")).sync()


class UnixTransport(unittest.TestCase):
    """The vault is reached over a Unix socket so that only its owner (and root)
    can connect, unlike a TCP port any local process can bind or use."""

    def serve(self, status, body):
        import http.server, json as _json, socket, socketserver, tempfile, threading

        seen = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def respond(self):
                seen["host"], seen["path"], seen["method"] = self.headers.get("Host"), self.path, self.command
                length = int(self.headers.get("Content-Length") or 0)
                seen["body"] = self.rfile.read(length) if length else b""
                payload = _json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = respond

            def log_message(self, *args):
                pass

            def address_string(self):
                return "unix"

        class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = f"{tmp.name}/bw.sock"
        server = Server(path, Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return path, seen

    # If this fails: bw serve's DNS-rebinding guard rejects every request over
    # the socket (it requires a Host of localhost:<port>), so nothing works.
    def test_sends_a_host_header_with_a_port(self):
        path, seen = self.serve(200, {"success": True, "data": {"template": {"status": "unlocked"}}})
        self.assertTrue(bv.Vault(bv.unix_transport(path)).is_unlocked())
        self.assertRegex(seen["host"], r"^localhost:\d+$")

    # If this fails: request bodies (item JSON) are not delivered over the socket.
    def test_post_body_arrives_intact(self):
        path, seen = self.serve(200, {"success": True, "data": {"id": "x"}})
        bv.unix_transport(path)("POST", "/object/item", {"a": [1, 2], "b": "\u00e9"})
        import json as _json
        self.assertEqual(_json.loads(seen["body"]), {"a": [1, 2], "b": "\u00e9"})

    # If this fails: a locked vault (HTTP 400 + envelope) is not recognised over
    # the socket, the same bug the TCP transport once had.
    def test_http_400_locked_is_vault_locked(self):
        path, _ = self.serve(400, {"success": False, "message": "Vault is locked."})
        with self.assertRaises(bv.VaultLocked):
            bv.Vault(bv.unix_transport(path)).list_passkeys()

    # If this fails: a missing socket (bw serve not started) looks like an empty
    # vault instead of a loud error.
    def test_missing_socket_is_a_vault_error(self):
        with self.assertRaises(bv.VaultError):
            bv.Vault(bv.unix_transport("/nonexistent/bw.sock")).sync()

    # If this fails: a non-envelope body (crash page) is trusted as vault data.
    def test_non_envelope_body_is_a_vault_error(self):
        path, _ = self.serve(502, {"oops": True})
        with self.assertRaises(bv.VaultError):
            bv.Vault(bv.unix_transport(path)).sync()


class HttpTransport(unittest.TestCase):
    # If this fails: a dead `bw serve` surfaces as a raw socket exception, or
    # worse as an empty result, instead of a VaultError the caller handles.
    def test_connection_refused_is_a_vault_error(self):
        call = bv.http_transport("http://localhost:1", timeout=2)
        with self.assertRaises(bv.VaultError):
            call("GET", "/status", None)


if __name__ == "__main__":
    unittest.main()
