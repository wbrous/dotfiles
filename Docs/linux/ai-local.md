# Local AI on Linux (Ollama + AMD iGPU via Vulkan)

Enable the AMD integrated GPU (Radeon 890M/880M, Strix) for Ollama on Arch via Vulkan.

## ollama reports library=cpu / drops the iGPU

**Symptom:** `ollama` uses CPU only, log says `dropping integrated GPU`, or GPU offload wanted on the root systemd service.

**Cause:** Stock `ollama` pkg is CPU-only; the Vulkan backend is the separate `ollama-vulkan` pkg (~44 MB — prefer over `ollama-rocm`, 3 GB with shaky iGPU gfx support). Two env vars are BOTH required: `OLLAMA_VULKAN=1` (no GPU discovery at all without it; not in `ollama serve --help`) and `OLLAMA_IGPU_ENABLE=1` (without it: `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1`). iGPU memory = GTT (~half of RAM, e.g. 15.8 GiB of 31 GiB), not the 512 MiB BIOS VRAM — a 9.2 GB Q8 model offloaded 29/33 layers.

**Fix:**
```sh
# 1. Probe without touching services (throwaway port):
OLLAMA_VULKAN=1 OLLAMA_IGPU_ENABLE=1 OLLAMA_HOST=127.0.0.1:11999 timeout 12 ollama serve 2>&1 | grep "inference compute"
# expect: library=Vulkan ... type=iGPU total="15.8 GiB"
sudo pacman -S ollama-vulkan
```
2. Drop-in `/etc/systemd/system/ollama.service.d/gpu.conf`:
```
[Service]
Environment="OLLAMA_VULKAN=1"
Environment="OLLAMA_IGPU_ENABLE=1"
```
```sh
sudo systemctl daemon-reload && sudo systemctl enable --now ollama
# Packaged unit runs as user `ollama` with OLLAMA_MODELS=/var/lib/ollama (NOT ~/.ollama/models):
cp -a ~/.ollama/models/. /var/lib/ollama/ && chown -R ollama:ollama /var/lib/ollama
sudo systemctl restart ollama   # always restart after enabling, then re-check (first start may still log library=cpu)
journalctl -u ollama -o cat | grep "inference compute"   # should say Vulkan
```
After loading a model the log shows `offloaded N/M layers to GPU` and `Vulkan0 model buffer size`.

**Notes:** `/dev/dri/renderD128` is 0666 so the `ollama` user needs no group changes; the unit's PrivateTmp/ProtectSystem/ProtectHome sandbox does NOT block Vulkan. Don't create a `systemd --user` ollama service when the root system service exists. For generation tests check model capabilities first (`/api/show`) — custom models may reject `/api/generate` and `/api/embed`. Raising BIOS UMA frame buffer might fit more layers (untested).

_Migrated from: ollama-amd-igpu-vulkan-arch_
