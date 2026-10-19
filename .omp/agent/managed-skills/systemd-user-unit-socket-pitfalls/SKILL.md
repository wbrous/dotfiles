---
name: systemd-user-unit-socket-pitfalls
description: "Debug systemd user services that fail to start or share unix sockets (missing ExecStart target, PrivateTmp hiding sockets, ReadWritePaths needing existing dirs, ProtectSystem private-run split, RuntimeDirectory wiping state)"
---

# systemd user-unit socket pitfalls

Five failures that look like app bugs but are unit sandboxing:

1. **ExecStart points at a path nothing installs.** Unit says
   `/usr/bin/my-cmd`, installer never links it there → `status=203/EXEC`.
   Fix: installer symlinks entry points into `/usr/local/bin`, units use
   the `/usr/local/bin/...` absolute path (NOT bare names; user PATH under
   systemd is not the login PATH).

2. **PrivateTmp hides unix sockets.** A service with `PrivateTmp=true`
   that binds `%t/.../sock` creates the socket inside its mount namespace;
   peers on the host path see nothing (service "active" yet no socket
   file). Fix: drop `PrivateTmp` on any service whose socket must be
   reachable from outside its namespace.

3. **ReadWritePaths requires pre-existing dirs.** `ReadWritePaths=%t/foo`
   fails the whole unit with `226/NAMESPACE` if `%t/foo` doesn't exist at
   startup. Fix: add `RuntimeDirectory=foo` (creates it before the
   namespace is built), keep `ReadWritePaths` for access.

4. **ProtectSystem=strict gives a private /run.** Even with `PrivateTmp=no`
   and `ReadWritePaths=%t/foo`, a `ProtectSystem=strict` service that binds
   a unix socket under `%t` creates it inside its own namespace: visible via
   `/proc/<PID>/root/run/...`, invisible on the host path. Service looks
   active, `ls` the host path shows nothing. Fix: drop `ProtectSystem` (and
   the now-ineffective `ReadWritePaths`) on socket-sharing services;
   `NoNewPrivileges=true` + a 0700 runtime dir is the sandbox.

5. **RuntimeDirectory without Preserve wipes state on restart.**
   `RuntimeDirectory=foo` without `RuntimeDirectoryPreserve=yes` deletes
   `%t/foo` on every restart — fatal if the credential/data store lives
   there (pull-then-restart looks like an empty store). Fix: add
   `RuntimeDirectoryPreserve=yes` to any unit whose runtime dir holds state
   that must survive restarts.

Debug order: `systemctl --user status`, then `journalctl --user -u <svc>`
for the real error (`203/EXEC`, `226/NAMESPACE`, or app-level bind fail),
then `ls` the socket path to confirm visibility. If the file is missing on
the host but present under `/proc/<MainPID>/root/...`, the bug is a
namespace split (cases 2 or 4), not the app.
