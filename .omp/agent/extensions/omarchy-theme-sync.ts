/**
 * Syncs the omp "omarchy" custom theme with the currently active Omarchy
 * theme on session start, then applies it live.
 *
 * The actual colors.toml -> omp theme JSON conversion (and persisting the
 * result as omp's theme.<mode> setting) lives in a shared script also
 * installed as Omarchy's `theme-set` hook, so switching themes mid-session
 * (outside omp) and starting omp both regenerate the same file:
 *   ~/.omp/omarchy-theme-sync.sh
 *
 * @precondition Omarchy is installed and has an active theme under
 *   ~/.local/state/omarchy/current/theme/colors.toml.
 * @postcondition ~/.omp/agent/themes/omarchy.json reflects the active
 *   Omarchy theme, and (in interactive mode) it is applied immediately.
 */

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

 const SYNC_SCRIPT = join(homedir(), ".omp/omarchy-theme-sync.sh");

function syncOmarchyTheme(): boolean {
  if (!existsSync(SYNC_SCRIPT)) return false;
  const result = spawnSync("bash", [SYNC_SCRIPT], { stdio: "ignore" });
  return result.status === 0;
}

function isFailedResult(value: unknown): value is { success: false; error?: unknown } {
  if (typeof value !== "object" || value === null || !("success" in value)) {
    return false;
  }
  return value.success === false;
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    let ok: boolean;
    try {
      ok = syncOmarchyTheme();
    } catch (err) {
      pi.logger.debug(`omarchy-theme-sync: sync failed: ${err}`);
      return;
    }
    if (!ok || !ctx.hasUI) return;

    const result = await ctx.ui.setTheme("omarchy");
    if (isFailedResult(result)) {
      pi.logger.debug(`omarchy-theme-sync: setTheme failed: ${result.error}`);
    }
  });
}
