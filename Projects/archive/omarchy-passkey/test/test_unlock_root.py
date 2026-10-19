"""Tests for the root unlock helper: it must never send the master password anywhere
but the invoking user's real `bw serve`.

The helper runs as root in production, but its decisions are plain functions, so they
are tested here as a normal user against REAL Unix sockets. The adversary is the user
themself (malware running as them), so the key tests stand up a listener owned by the
same uid that is not bw and check it never receives a byte of the password.
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

HELPER = os.path.join(os.path.dirname(__file__), "..", "libexec", "omarchy-passkey-unlock-root")
loader = importlib.machinery.SourceFileLoader("unlock_root", HELPER)
spec = importlib.util.spec_from_loader("unlock_root", loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)

PASSWORD = b"s3cr3t pass!"


class Listener:
    """A real Unix-socket HTTP-ish server. Records every byte it is sent."""

    def __init__(self, path, reply=None):
        self.received = b""
        self.reply = reply if reply is not None else {"success": True, "data": {}}
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        conn.settimeout(2)
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            head, _, rest = data.partition(b"\r\n\r\n")
            length = 0
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-length"):
                    length = int(line.split(b":")[1])
            while len(rest) < length:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                rest += chunk
            # Exactly what arrived: empty if the client sent nothing at all.
            self.received = data + rest[len(data.partition(b"\r\n\r\n")[2]):]
            payload = json.dumps(self.reply).encode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (len(payload), payload))
        except (OSError, ValueError):
            pass
        finally:
            conn.close()

    def close(self):
        self.sock.close()
        self.thread.join(3)


class Harness(unittest.TestCase):
    """Runs helper.main() against a Listener, as if it were the user's bw serve."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "bw.sock")

    def run_main(self, listener, *, as_bw, secret=PASSWORD):
        """`as_bw` decides whether the peer counts as /usr/bin/bw. The REAL
        verify_peer logic runs either way; only the exe string we compare against
        moves, because the test process is python, not bw."""
        uid = os.getuid()
        real_exe = os.readlink(f"/proc/{os.getpid()}/exe")
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"PKEXEC_UID": str(uid)}), \
             mock.patch.object(sys, "argv", ["x"]), \
             mock.patch.object(sys, "stderr", stderr), \
             mock.patch.object(helper, "socket_path_for", return_value=self.path), \
             mock.patch.object(helper, "BW_BINARY", real_exe if as_bw else "/usr/bin/bw"), \
             mock.patch.object(helper, "read_secret", return_value=secret):
            try:
                code = helper.main()
            except SystemExit as exc:
                code = exc.code
        listener.thread.join(3)
        return code, stderr.getvalue()


class PeerVerification(Harness):
    """The reason this design exists: a same-user impostor must get nothing."""

    # If this fails: a listener that is not bw (a same-user process that swapped the
    # socket) receives the master password. This is THE vulnerability.
    def test_impostor_listener_never_receives_the_password(self):
        impostor = Listener(self.path)
        self.addCleanup(impostor.close)
        code, _ = self.run_main(impostor, as_bw=False)
        self.assertEqual(code, 1)
        self.assertEqual(impostor.received, b"", "the impostor was sent bytes")
        self.assertNotIn(PASSWORD, impostor.received)

    # If this fails: even a correct peer is refused and the feature never works.
    def test_genuine_listener_gets_the_password_in_the_body(self):
        genuine = Listener(self.path)
        self.addCleanup(genuine.close)
        code, _ = self.run_main(genuine, as_bw=True)
        self.assertEqual(code, 0)
        head, _, body = genuine.received.partition(b"\r\n\r\n")
        self.assertEqual(json.loads(body), {"password": PASSWORD.decode()})
        self.assertTrue(head.startswith(b"POST /unlock HTTP/1.1"))
        self.assertNotIn(PASSWORD, head, "password leaked into the request line or headers")

    # If this fails: the helper decrypts the secret before knowing who is listening,
    # so an impostor connection at least costs a decryption and widens the window the
    # plaintext sits in memory.
    def test_secret_is_not_even_decrypted_for_an_impostor(self):
        impostor = Listener(self.path)
        self.addCleanup(impostor.close)
        calls = []
        with mock.patch.object(helper, "read_secret", side_effect=lambda: calls.append(1) or PASSWORD):
            uid = os.getuid()
            with mock.patch.dict(os.environ, {"PKEXEC_UID": str(uid)}), \
                 mock.patch.object(sys, "argv", ["x"]), \
                 mock.patch.object(sys, "stderr", io.StringIO()), \
                 mock.patch.object(helper, "socket_path_for", return_value=self.path), \
                 self.assertRaises(SystemExit):
                helper.main()
        self.assertEqual(calls, [], "read_secret ran before the peer was verified")

    # If this fails: a listener running as a different uid is trusted if it happens
    # to be called bw. The uid check is independent of the exe check.
    def test_listener_with_a_different_uid_is_refused(self):
        listener = Listener(self.path)
        self.addCleanup(listener.close)
        real_exe = os.readlink(f"/proc/{os.getpid()}/exe")
        with mock.patch.object(helper, "BW_BINARY", real_exe):
            with mock.patch.object(helper, "peer_credentials", return_value=(os.getpid(), os.getuid() + 1)):
                sock = socket.socket(socket.AF_UNIX)
                sock.connect(self.path)
                self.addCleanup(sock.close)
                with self.assertRaises(SystemExit) as caught, mock.patch.object(sys, "stderr", io.StringIO()):
                    helper.verify_peer(sock, os.getuid())
        self.assertEqual(caught.exception.code, 1)

    # If this fails: peer credentials are not read from the kernel on the CONNECTED
    # socket, so swapping the file after a path check would still work.
    def test_peer_credentials_come_from_the_kernel(self):
        listener = Listener(self.path)
        self.addCleanup(listener.close)
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(self.path)
        self.addCleanup(sock.close)
        self.assertEqual(helper.peer_credentials(sock), (os.getpid(), os.getuid()))


class Refusals(unittest.TestCase):
    # If this fails: the helper can be run directly, bypassing the fingerprint gate
    # that only pkexec enforces.
    def test_refuses_without_pkexec_uid(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                helper.invoking_uid()
        self.assertEqual(caught.exception.code, 1)

    # If this fails: a crafted PKEXEC_UID is accepted as a user id.
    def test_rejects_non_numeric_uid(self):
        for bad in ("", "abc", "-1", "1000 ", "0x10", "1e3"):
            with self.subTest(bad=bad), mock.patch.dict(os.environ, {"PKEXEC_UID": bad}), \
                 mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
                helper.invoking_uid()

    # If this fails: root could be tricked into unlocking its own vault.
    def test_refuses_uid_zero(self):
        with mock.patch.dict(os.environ, {"PKEXEC_UID": "0"}), mock.patch.object(sys, "stderr", io.StringIO()), \
             self.assertRaises(SystemExit):
            helper.invoking_uid()

    # If this fails: an argument (a socket path, a URL) steers where the password goes.
    def test_refuses_any_argument(self):
        with mock.patch.object(sys, "argv", ["x", "/tmp/evil.sock"]), mock.patch.object(sys, "stderr", io.StringIO()), \
             self.assertRaises(SystemExit):
            helper.main()

    # If this fails: the socket is not derived purely from the (unforgeable) uid.
    def test_socket_path_depends_only_on_uid(self):
        self.assertEqual(helper.socket_path_for(1000), "/run/user/1000/omarchy-passkey/bw.sock")
        self.assertEqual(helper.socket_path_for(1234), "/run/user/1234/omarchy-passkey/bw.sock")


class SealedCredential(unittest.TestCase):
    """Only a root-owned, private regular file may be decrypted and sent."""

    def stat_result(self, mode, uid):
        return os.stat_result((mode, 0, 0, 1, uid, 0, 0, 0, 0, 0))

    def refusal_code(self, st):
        with mock.patch.object(helper.os, "lstat", return_value=st), mock.patch.object(sys, "stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                helper.read_secret()
        return caught.exception.code

    # If this fails: a user-owned or readable file is trusted, so a user could plant
    # their own sealed blob for root to decrypt and forward.
    def test_refuses_files_that_are_not_root_private_regular_files(self):
        import stat as st
        for mode, uid in (
            (st.S_IFREG | 0o640, 0),
            (st.S_IFREG | 0o604, 0),
            (st.S_IFREG | 0o600, 1000),
            (st.S_IFLNK | 0o777, 0),
            (st.S_IFDIR | 0o700, 0),
        ):
            with self.subTest(mode=oct(mode), uid=uid):
                self.assertEqual(self.refusal_code(self.stat_result(mode, uid)), 3)

    # If this fails: a missing credential crashes instead of telling the user to enrol.
    def test_missing_credential_is_exit_3(self):
        with mock.patch.object(helper.os, "lstat", side_effect=FileNotFoundError), \
             mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as caught:
            helper.read_secret()
        self.assertEqual(caught.exception.code, 3)

    # If this fails: a failed or empty decryption is sent as an empty password.
    def test_failed_or_empty_decryption_is_exit_3(self):
        import stat as st
        good = self.stat_result(st.S_IFREG | 0o600, 0)
        for returncode, stdout in ((1, b"x"), (0, b""), (0, b"\n")):
            completed = mock.Mock(returncode=returncode, stdout=stdout)
            with self.subTest(rc=returncode, out=stdout), mock.patch.object(helper.os, "lstat", return_value=good), \
                 mock.patch.object(helper.subprocess, "run", return_value=completed), \
                 mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as caught:
                helper.read_secret()
            self.assertEqual(caught.exception.code, 3)

    # If this fails: decryption inherits the caller's environment (a user-controlled
    # PATH/LD_PRELOAD in the pkexec'd process) or an attacker-chosen binary.
    def test_decrypts_with_a_fixed_binary_a_fixed_name_and_an_empty_environment(self):
        import stat as st
        good = self.stat_result(st.S_IFREG | 0o600, 0)
        completed = mock.Mock(returncode=0, stdout=b"hunter2\n")
        with mock.patch.object(helper.os, "lstat", return_value=good), \
             mock.patch.object(helper.subprocess, "run", return_value=completed) as run:
            self.assertEqual(helper.read_secret(), b"hunter2")
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "/usr/bin/systemd-creds")
        self.assertIn("--name=omarchy-passkey-master", argv)
        self.assertEqual(run.call_args.kwargs["env"], {})


class ServerReplies(Harness):
    # If this fails: a wrong password looks like success.
    def test_server_refusal_is_exit_2(self):
        server = Listener(self.path, reply={"success": False, "message": "Cryptography error"})
        self.addCleanup(server.close)
        code, _ = self.run_main(server, as_bw=True)
        self.assertEqual(code, 2)

    # If this fails: the password is echoed into an error that reaches the journal or
    # the polkit agent.
    def test_error_output_never_contains_the_password(self):
        server = Listener(self.path, reply={"success": False, "message": "Cryptography error"})
        self.addCleanup(server.close)
        _, stderr = self.run_main(server, as_bw=True)
        self.assertNotIn("s3cr3t", stderr)

    # If this fails: bw serve's DNS-rebinding guard rejects the request (403).
    def test_sends_the_host_header_bw_serve_requires(self):
        server = Listener(self.path)
        self.addCleanup(server.close)
        self.run_main(server, as_bw=True)
        self.assertIn(b"Host: localhost:8087", server.received)

    # If this fails: a missing server hangs or tracebacks instead of a clean exit 2.
    def test_no_server_is_exit_2(self):
        with mock.patch.dict(os.environ, {"PKEXEC_UID": str(os.getuid())}), mock.patch.object(sys, "argv", ["x"]), \
             mock.patch.object(helper, "socket_path_for", return_value="/nonexistent/bw.sock"), \
             mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as caught:
            helper.main()
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
