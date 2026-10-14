---
name: omp-generate-image-enable-and-use
description: "User asks to generate an image or \"image subagent\" in omp and no image tool is visible; enable and call generate_image."
---

# Generating images in omp

There is no image subagent. Image generation is a built-in, setting-gated tool: `generate_image`. It is off by default (`generate_image.enabled: false`), so it does not show in the tool inventory or in `xd://` listings.

## Procedure
1. Do not spend turns on web search. Read `cfg://generate_image` to confirm the setting.
2. Check `cfg://modelRoles` for an `image` role (for example `google-antigravity/gemini-3-pro-image`). If one exists, credentials are already handled. Otherwise one of OPENAI/XAI/OPENROUTER/GEMINI/GOOGLE_API_KEY, or a /login, is required.
3. Writes to `cfg://` need user approval. Use `ask` first (session-only vs persist), then write `true` to `cfg://generate_image/enabled`. After a session-only write, ask whether to save it. Saving means writing `true` to `cfg://generate_image/enabled/save`.
4. Read `xd://generate_image` for the schema, then write JSON to it. `subject` is required. Optional fields include `action`, `scene`, `composition`, `lighting`, `style`, `text`, `aspect_ratio` (16:9, 1:1, ...), `input[]` for edits, and `model`.
5. The tool returns a path like `/tmp/omp-image-*.jpg`. Open it with `read` to verify it visually before reporting.

## Notes
- The model may add a faint signature in a corner. Mention it if it is visible.
- If the user gives no subject, ask once. "Surprise me" is acceptable, so pick something simple.
