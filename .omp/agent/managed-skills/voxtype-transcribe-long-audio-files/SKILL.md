---
name: voxtype-transcribe-long-audio-files
description: "Transcribe long audio files (voice memos .qta/.m4a, lectures) with voxtype CLI on Linux; WAV conversion, log stripping, parallel runs, whisper repetition loops."
---

# Transcribing long audio with voxtype

## Procedure
1. `voxtype transcribe` only accepts 16 kHz mono WAV. Convert first (fast, ~1s per 30 min):
   `ffmpeg -nostdin -v error -y -i in.qta -vn -ar 16000 -ac 1 -c:a pcm_s16le out.wav`
   (ffprobe/ffmpeg read Apple `.qta` fine.)
2. Run `voxtype transcribe out.wav`. **Stdout contains log/header lines mixed with the transcript** (`Loading audio file`, `Audio format`, `Processing`, ISO-timestamp `INFO` lines). Strip them:
   `voxtype transcribe f.wav 2>/dev/null | grep -v -E '^(Loading audio|Audio format|Processing|20[0-9]{2}-[0-9]{2}-[0-9]{2}T|$)' > f.txt`
   The transcript body is one long line.
3. Check config/models with `voxtype config` and `voxtype info models`. Default here: Whisper `small.en` (installed); medium/large-v3-turbo need downloading. `--model` and `--engine` override.

## Performance
- One run uses ~4 cores (user time ~4x real). Speed ~ 6x realtime with small.en (30 min audio = ~5.5 min) on a 24-core box.
- Multiple files: run them in parallel as separate background processes (user asked for this); do NOT run sequentially. When relaunching, kill the old sequential job first, or two processes write the same output file. Use `pgrep -af 'voxtype transcribe'` to check for strays.
- Don't `time` inside a backgrounded subshell and expect the log to be reliable.

## Quality check
Whisper small.en on noisy multi-speaker audio (classroom/group chat) can fall into **repetition loops** (one sentence repeated 40-90x). Detect with:
`tr '.?!' '\n\n\n' < f.txt | sed 's/^ *//' | grep -v '^$' | sort | uniq -c | sort -rn | head`
If a sentence repeats dozens of times, those stretches are lost; offer a re-run with a larger model (medium.en / large-v3-turbo, needs download, ~2-3x slower) rather than presenting the transcript as reliable.

Related: `arch-iphone-voice-memos-from-backup` for getting the .qta files off the phone.
