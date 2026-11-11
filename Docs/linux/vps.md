# VPS Work: Provisioning, Fork Sync, SSH Recovery

Provision a blank Ubuntu VPS over password SSH; sync one forked subfolder from upstream; recover SSH after reboot.

## Provision a blank Ubuntu VPS (password SSH)

**Symptom:** Handed a blank Ubuntu VPS with `root@IP` + password; need it ready for Docker deploys without touching the repo yet.

**Fix — local sandbox prereqs:** `sshpass` (Arch: `sudo pacman -S sshpass`). Never put the password on the command line: `export SSHPASS='...'` then `sshpass -e ssh`.
```sh
sshpass -e ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 root@IP "cat /etc/os-release; uname -m; nproc; free -h; df -h /"
# expect Ubuntu (24.04/26.04), x86_64; note RAM/disk
sshpass -e ssh root@IP "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl ca-certificates gnupg lsb-release"
# Docker GPG -> /etc/apt/keyrings/docker.asc, repo https://download.docker.com/linux/ubuntu <codename> stable (codename from /etc/os-release)
# gh GPG -> /etc/apt/keyrings/githubcli-archive-keyring.gpg, repo https://cli.github.com/packages stable main
sshpass -e ssh root@IP "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin gh"
sshpass -e ssh root@IP "systemctl enable --now docker; docker run --rm hello-world"
sshpass -e ssh root@IP "apt-get install -y -qq unzip && curl -fsSL https://bun.sh/install | bash"
# persist PATH in /root/.bashrc: export BUN_INSTALL="$HOME/.bun"; export PATH="$BUN_INSTALL/bin:$PATH"
```
STOP before cloning. Leave `gh auth login` to the user (offer to run it and relay the device code).

**Gotchas:** Bun installer fails with `unzip is required` on minimal images — install `unzip` first. First SSH prints the post-quantum key-exchange warning; harmless. Do not clone any repo or run `gh auth login` unasked.

_Migrated from: blank-ubuntu-vps-provision_

## Sync one forked subfolder from upstream, preserving local edits

**Symptom:** A private fork (e.g. `zep-dev-ai/oh-my-pi` of `can1357/oh-my-pi`) keeps only one subdirectory (e.g. `python/robomp`) in sync — a full-repo merge would risk unrelated infra files diverging or crashing a production self-hosted setup.

**Fix (in the target checkout, e.g. over SSH on the VPS):**
```bash
cd /path/to/fork/checkout
git add path/to/subfolder && git commit -m "..."   # commit pending locals first
git remote add upstream https://github.com/<owner>/<repo> 2>&1  # ok if already exists
git fetch upstream main
git log --oneline HEAD..upstream/main -- path/to/subfolder   # upstream-only commits
git log --oneline upstream/main..HEAD -- path/to/subfolder   # local-only commits
# If local-only commits are re-authored copies of the same upstream commits
# (fork-sync bots rewrite author), there is nothing to preserve — don't cherry-pick back.
git checkout upstream/main -- path/to/subfolder   # overwrites ONLY that subfolder, unlike merge
git status --short   # review touched files before committing
# Reapply real local customizations (compose env passthroughs, extra_hosts IP pins):
# diff pre-sync vs new upstream, hand-reapply meaningful hunks (str.replace one-liner over SSH is fine).
git add path/to/subfolder && git commit -m "sync: update from upstream"
```
Verify: `python3 -m py_compile` changed sources; `docker compose config -q`; grep new env refs (`grep -oE 'ROBOMP_[A-Z_]+' src/config.py`) have safe defaults; `docker compose build` then confirm the image contains upstream's new files (`docker run --rm --entrypoint sh <image> -c 'ls ...; grep -c ...'` — don't trust instant BuildKit-cached logs); `docker compose up -d --force-recreate <service...>` then tail logs and smoke-test (`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/`).

_Migrated from: vps-fork-subtree-sync-and-console-recovery_

## Recover VPS SSH after reboot (connection refused)

**Symptom:** SSH gives `Connection refused` on port 22 (not a timeout — host is up, `ping` works; nothing listens on 22). After a provider-console reboot this flaps briefly and self-resolves — poll before escalating; if it persists past a couple minutes, use the provider VNC/serial console (network diagnosis is impossible when SSH itself is down).

**Cause/Fix (on the console as root — don't assume the unit name):** Debian/Ubuntu: `systemctl status ssh` (NOT `sshd` — that unit doesn't exist there); RHEL/Fedora: `systemctl status sshd`.
```bash
systemctl status ssh              # or sshd — try the other name if "could not be found"
journalctl -u ssh -n 50 --no-pager
ss -tlnp | grep :22
systemctl restart ssh
ufw status verbose                 # active-with-no-22-rule or default-deny blocks even running sshd
ufw allow 22/tcp && ufw reload
iptables -L INPUT -n --line-numbers | head -30   # second firewall layer independent of ufw
```
Containers with `restart: unless-stopped` come back on their own — verify with `docker ps --format '{{.Names}}: {{.Status}}'`; only force-recreate ones whose image actually changed.

_Migrated from: vps-fork-subtree-sync-and-console-recovery_
