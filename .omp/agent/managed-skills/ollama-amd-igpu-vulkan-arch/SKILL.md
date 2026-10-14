---
name: ollama-amd-igpu-vulkan-arch
description: "Enable AMD iGPU (Radeon 890M/880M, Strix) for ollama on Arch via Vulkan; ollama reports library=cpu, 'dropping integrated GPU', or user wants GPU offload on the root systemd service."
---

# Enable AMD iGPU for ollama (Arch, Vulkan)

## Facts learned (Ryzen AI 9 HX 370 / Radeon 890M, ollama 0.40.4)
- Stock `ollama` pkg is CPU-only. Vulkan backend is the separate pkg `ollama-vulkan` (~44 MB). Prefer it over `ollama-rocm` (3 GB, iGPU gfx support shaky).
- Need BOTH env vars: `OLLAMA_VULKAN=1` (without it, no GPU discovery at all) and `OLLAMA_IGPU_ENABLE=1` (otherwise log says `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1`). `OLLAMA_VULKAN` is NOT in `ollama serve --help`; find it by testing.
- iGPU memory = GTT (~half of RAM, e.g. 15.8 GiB of 31 GiB), not the 512 MiB BIOS VRAM. A 9.2 GB Q8 model offloaded 29/33 layers.
- Packaged unit `/usr/lib/systemd/system/ollama.service` runs as user `ollama`, `OLLAMA_MODELS=/var/lib/ollama` (NOT `~/.ollama/models`), so copy models over: `cp -a ~/.ollama/models/. /var/lib/ollama/ && chown -R ollama:ollama /var/lib/ollama`.
- `/dev/dri/renderD128` is 0666 so the `ollama` user needs no group changes; the unit's PrivateTmp/ProtectSystem/ProtectHome sandbox was bisected and does NOT block Vulkan.

## Procedure
1. Probe without touching services (throwaway port): `OLLAMA_VULKAN=1 OLLAMA_IGPU_ENABLE=1 OLLAMA_HOST=127.0.0.1:11999 timeout 12 ollama serve 2>&1 | grep "inference compute"` -> expect `library=Vulkan ... type=iGPU total="15.8 GiB"`.
2. `sudo pacman -S ollama-vulkan`
3. Drop-in `/etc/systemd/system/ollama.service.d/gpu.conf`:
   ```
   [Service]
   Environment="OLLAMA_VULKAN=1"
   Environment="OLLAMA_IGPU_ENABLE=1"
   ```
4. `sudo systemctl daemon-reload && sudo systemctl enable --now ollama`, copy models (above).
5. Verify: `journalctl -u ollama -o cat | grep "inference compute"` should say Vulkan. After loading a model, log shows `offloaded N/M layers to GPU` and `Vulkan0 model buffer size`.

## Gotchas
- Right after first enabling, the service log showed `library=cpu` even though env was set (reason not determined [INFERENCE]: first-start discovery); a `sudo systemctl restart ollama` fixed it. Always restart then re-check.
- sudo here needs fingerprint: run via bash with `pty: true` (see skill sudo-interactive-tty-via-hub). Write multi-step root work to a /tmp script and `sudo bash` it once.
- Don't make a `systemd --user` ollama service if a root system service exists; the user wanted the root one.
- To test generation, check model capabilities first (`/api/show`); custom models may reject /api/generate and /api/embed.
- Optional: raising BIOS UMA frame buffer might fit more layers (untested).
