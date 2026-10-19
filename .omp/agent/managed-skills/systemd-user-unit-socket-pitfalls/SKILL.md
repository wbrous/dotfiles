---
name: systemd-user-unit-socket-pitfalls
description: "Debug systemd user services that fail to start or share unix sockets (missing ExecStart target, PrivateTmp hiding sockets, ReadWritePaths needing existing dirs, ProtectSystem=strict private /run)"
---

# systemd user-unit socket pitfalls

Four failures that look like app bugs but are unit sandboxing:

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
4. **ProtectSystem=strict gives a private /run.** Even with PrivateTmp
   removed, `ProtectSystem=strict` mounts a private `/run`: the socket
   exists inside the namespace (visible via
   `/proc/<mainpid>/root/run/...`), invisible on the host path.
   `ReadWritePaths` does not punch through for the socket file itself.
   Fix: drop `ProtectSystem` on socket-sharing services; rely on
   `NoNewPrivileges` + a 0700 `RuntimeDirectory` for the sandbox.
   `ReadWritePaths` without `ProtectSystem` is a no-op — remove it too.

Debug order: `systemctl --user status`, then `journalctl --user -u <svc>`
for the real error (`203/EXEC`, `226/NAMESPACE`, or app-level bind fail),
then `ls` the socket path to confirm visibility, then compare with
`ls /proc/<mainpid>/root/<socket-path>` (no sudo needed) to detect a
namespace split: socket present under `/proc/.../root` but absent on the
host = sandbox mount problem, not an app bug.
