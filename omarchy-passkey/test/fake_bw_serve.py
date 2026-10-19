"""A stand-in for `bw serve` for end-to-end runs that must not touch a real vault.

Behaves as observed against the real server: errors are HTTP 400 with the
{"success": false, "message": ...} envelope, /status is always 200 and reports
locked/unlocked, data routes refuse while locked, items persist to a JSON file so
a restart of the *test* keeps them (like a real server-side vault would).

Usage: fake_bw_serve.py PORT STATE_FILE PASSWORD
"""

import http.server
import socket
import json
import sys
import uuid

PORT, STATE_FILE, PASSWORD = int(sys.argv[1]), sys.argv[2], sys.argv[3]
state = {"unlocked": False}


def load():
    try:
        return json.load(open(STATE_FILE))
    except FileNotFoundError:
        return {}


def save(items):
    json.dump(items, open(STATE_FILE, "w"))


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def ok(self, data):
        self.reply(200, {"success": True, "data": data})

    def fail(self, message):
        self.reply(400, {"success": False, "message": message})

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length)) if length else None

    def route(self, method):
        if self.headers.get("Origin"):
            return self.reply(403, {"success": False, "message": "forbidden"})
        path = self.path
        if (method, path) == ("GET", "/status"):
            status = "unlocked" if state["unlocked"] else "locked"
            return self.ok({"object": "template", "template": {"status": status}})
        if (method, path) == ("POST", "/unlock"):
            if (self.body() or {}).get("password") == PASSWORD:
                state["unlocked"] = True
                return self.ok({"object": "message", "title": "Your vault is now unlocked!"})
            return self.fail("Cryptography error, The decryption operation failed")
        if not state["unlocked"]:
            return self.fail("Vault is locked.")
        items = load()
        if (method, path) == ("POST", "/sync"):
            return self.ok({"object": "message", "title": "Syncing complete."})
        if (method, path) == ("GET", "/list/object/items"):
            return self.ok({"object": "list", "data": list(items.values())})
        if (method, path) == ("POST", "/object/item"):
            item = self.body()
            item["id"] = str(uuid.uuid4())
            items[item["id"]] = item
            save(items)
            return self.ok(item)
        if path.startswith("/object/item/"):
            item_id = path.rsplit("/", 1)[1]
            if item_id not in items:
                return self.fail("Not found.")
            if method == "GET":
                return self.ok(items[item_id])
            if method == "PUT":
                items[item_id] = self.body()
                save(items)
                return self.ok(items[item_id])
        return self.fail(f"unrouted {method} {path}")

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def log_message(self, *args):
        pass


class Ipv6Server(http.server.ThreadingHTTPServer):
    """The real `bw serve` listens on [::1] only, so the stand-in must too."""

    address_family = socket.AF_INET6


Ipv6Server(("::1", PORT), Handler).serve_forever()
