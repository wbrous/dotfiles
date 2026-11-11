# systemd User Units: Socket-Sharing Pitfalls

Five failures that look like app bugs but are unit sandboxing. Debug order: `systemctl --user status`, then `journalctl --user -u <svc>` (real error: `203/EXEC`, `226/NAMESPACE`, or app bind fail), then `ls` the socket path. If the file is missing on the host but present under `/proc/<MainPID>/root/...`, it's a namespace split (cases 2/4), not the app.

## ExecStart points at a path nothing installs

**Symptom:** `status=203/EXEC`.

**Cause:** Unit says `/usr/bin/my-cmd` but the installer never links it there.

**Fix:** Installer symlinks entry points into `/usr/local/bin`; units use the `/usr/local/bin/...` absolute path (NOT bare names — user PATH under systemd is not the login PATH).

## PrivateTmp hides unix sockets

**Symptom:** Service "active" yet no socket file at the host path.

**Cause:** With `PrivateTmp=true`, a service binding `%t/.../sock` creates the socket inside its mount namespace; peers on the host path see nothing.

**Fix:** Drop `PrivateTmp` on any service whose socket must be reachable from outside its namespace.

## ReadWritePaths requires pre-existing dirs

**Symptom:** Whole unit fails with `226/NAMESPACE`.

**Cause:** `ReadWritePaths=%t/foo` fails if `%t/foo` doesn't exist at startup.

**Fix:** Add `RuntimeDirectory=foo` (created before the namespace is built); keep `ReadWritePaths` for access.

## ProtectSystem=strict gives a private /run

**Symptom:** Service active, host socket path empty — even with `PrivateTmp=no` and `ReadWritePaths=%t/foo`.

**Cause:** `ProtectSystem=strict` services binding under `%t` create the socket in their own namespace (visible via `/proc/<PID>/root/run/...`, invisible on host).

**Fix:** Drop `ProtectSystem` (and the now-ineffective `ReadWritePaths`) on socket-sharing services; `NoNewPrivileges=true` + a 0700 runtime dir is the sandbox.

## RuntimeDirectory without Preserve wipes state on restart

**Symptom:** Pull-then-restart looks like an empty store.

**Cause:** `RuntimeDirectory=foo` without `RuntimeDirectoryPreserve=yes` deletes `%t/foo` on every restart — fatal if the credential/data store lives there.

**Fix:** Add `RuntimeDirectoryPreserve=yes` to any unit whose runtime dir holds state that must survive restarts.

_Migrated from: systemd-user-unit-socket-pitfalls_
