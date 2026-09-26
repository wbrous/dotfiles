---
name: blank-ubuntu-vps-provision
description: "Provision a blank Ubuntu VPS over password SSH with git, Docker+compose, gh CLI, and bun, stopping before repo clone/gh-auth."
---

# Blank Ubuntu VPS Provision (password SSH)

Use when handed a blank Ubuntu VPS with `root@IP` + password and asked to prepare it for Docker-based deploys without touching the repo yet.

## Prerequisites on local sandbox

- `sshpass` (Arch: `sudo pacman -S sshpass`).
- Never put the password in the command line; always `export SSHPASS='...'` then `sshpass -e ssh`.

## Steps

1. Recon (accept host key on first connect only):
   `sshpass -e ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 root@IP "cat /etc/os-release; uname -m; nproc; free -h; df -h /"`
   Expect Ubuntu (24.04/26.04), x86_64. Note RAM/disk.
2. Base packages:
   `apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl ca-certificates gnupg lsb-release`
3. Add Docker + GitHub CLI apt repos, then install:
   - Docker GPG to `/etc/apt/keyrings/docker.asc`, repo `https://download.docker.com/linux/ubuntu <codename> stable` (codename from `/etc/os-release`, e.g. `resolute`).
   - gh GPG to `/etc/apt/keyrings/githubcli-archive-keyring.gpg`, repo `https://cli.github.com/packages stable main`.
   - `apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin gh`
4. Enable + verify Docker: `systemctl enable --now docker; docker run --rm hello-world`.
5. Bun needs `unzip` first: `apt-get install -y -qq unzip`, then `curl -fsSL https://bun.sh/install | bash`. Persist PATH in `/root/.bashrc`:
   `export BUN_INSTALL="$HOME/.bun"; export PATH="$BUN_INSTALL/bin:$PATH"`.
6. STOP before cloning. Leave `gh auth login` to the user (offer to run it and relay the device code).

## Gotchas

- Bun installer fails with `unzip is required` on minimal images; install `unzip` first.
- First SSH always prints the post-quantum key-exchange warning; harmless.
- Do not clone any repo or run `gh auth login` unasked; the user explicitly wants that gate.
