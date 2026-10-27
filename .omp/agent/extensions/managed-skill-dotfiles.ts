// managed-skill-dotfiles: auto-backup every successful `manage_skill` outcome
// (create/update/delete) for managed skills (~/.omp/agent/managed-skills/<name>/)
// into the dotfiles bare repo (~/.dotfiles) the moment the tool lands.
//
// Motivation: when omp creates, updates, or deletes a managed skill via
// `manage_skill`, it writes to disk but does not touch the dotfiles repo, so
// the change is left unsynced until a manual fan-out scout survey. This
// extension closes that gap: every mutation is committed with the repo's
// existing `Add managed-skill: <name>` convention (create/update), and deletes
// are committed too (`git rm`) so the backup copy tracks the on-disk truth.
//
// Notifications (commit/block/anomaly reports) are delivered with
// `deliverAs: "nextTurn"` — NO `triggerTurn` — so they ride along with the
// next real user message instead of scheduling their own continuation turn.
// This avoids burning a token-costing turn right before omp's autolearn may
// capture a new skill from the same session.
//
// Guardrails:
//   - Never `add -A`/`git rm -r`; only the single <name>/SKILL.md path.
//   - Skip commits when the file is byte-identical to HEAD (no no-op commit
//     noise in the "what's actually new" signal); skip deletes of skills that
//     were never tracked (nothing to remove).
//   - Never bypass the global gitleaks pre-commit hook (GIT_ALLOW_SECRETS=1 is
//     a deliberate human escape hatch). If the commit is blocked, surface the
//     hook's stderr via sendMessage so the agent/user can decide.
//   - De-duplicate in-flight ops per skill name so two rapid mutations of the
//     same skill can't race the bare-repo commit.
//   - Never calls `manage_skill`, so it can never re-trigger itself.
import { statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/** Root of the isolated managed-skills store. */
const MANAGED_SKILLS_DIR = join(homedir(), ".omp", "agent", "managed-skills");

/** Dotfiles bare repo. */
const DOTFILES_DIR = join(homedir(), ".dotfiles");

/** Verify the on-disk skill dir exists and holds a SKILL.md (cheap, no API dep). */
function skillExistsOnDisk(name: string): boolean {
	try {
		const st = statSync(join(MANAGED_SKILLS_DIR, name, "SKILL.md"));
		return st.isFile();
	} catch {
		return false;
	}
}

/** Single-quote a shell token so the sh wrapper cannot be tricked into running anything but git. */
function shq(s: string): string {
	return `'${s.replace(/'/g, `'\\''`)}'`;
}

interface BareGit {
	args: string[];
	stdout: string;
	stderr: string;
	code: number;
}

/**
 * Run a git command against the dotfiles bare repo via pi.exec.
 *
 * Uses `git --git-dir=… --work-tree=…` leading global options (the exact
 * expansion of the `dotfiles` shell alias) rather than GIT_DIR/GIT_WORK_TREE
 * env vars, because pi.exec's ExecOptions does not forward `env` — the git
 * command must point at the bare repo itself, not inherit the caller's env.
 *
 * Runs the command through a shell with `OMPCODE=1` prefixed on the argv (the
 * way the harness itself seeds agent subprocesses) so the shared
 * `prepare-commit-msg` hook (git-scoped-coauthor-trailer skill) appends the
 * `Co-authored-by: wbrous-dev-ai` trailer to the commit. Every arg is
 * single-quoted so the deliberately-shallow shell wrapper cannot be tricked by
 * the skill name or paths into running anything other than git itself.
 */
async function bareGit(pi: ExtensionAPI, ...args: string[]): Promise<BareGit> {
	const argv = ["git", `--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args];
	const cmd = `OMPCODE=1 ${argv.map(shq).join(" ")}`;
	const result = await pi.exec("/bin/sh", ["-c", cmd], { cwd: homedir() });
	return { args, stdout: result.stdout, stderr: result.stderr, code: result.code };
}

export default function managedSkillDotfilesExtension(pi: ExtensionAPI): void {
	/** Guard against overlapping ops for the same skill name. */
	const inFlight = new Set<string>();

	async function syncSkillToDotfiles(input: Record<string, unknown>): Promise<void> {
		const action = input.action;
		const name = input.name;
		if (typeof name !== "string" || !name || (action !== "create" && action !== "update" && action !== "delete")) {
			return;
		}

		// If an op for this name is already in flight, let it absorb this one —
		// the running commit will already have staged the latest file content.
		if (inFlight.has(name)) return;
		inFlight.add(name);
		try {
			const repoRelPath = `.omp/agent/managed-skills/${name}/SKILL.md`;

			// The path the managed skill is expected to live at (or have lived
			// at, for a delete). Refuse to guess a path and add something wrong.
			const diskPath = join(MANAGED_SKILLS_DIR, name, "SKILL.md");
			const onDisk = skillExistsOnDisk(name);

			if (action === "delete") {
				if (onDisk) {
					// manage_skill said the skill was deleted but the file is still
					// here — that is unexpected. Leave the dotfiles copy alone.
					pi.sendMessage(
						{
							customType: "managed-skill-dotfiles",
							content:
								`manage_skill reported deleting "${name}", but ${diskPath} still exists. ` +
								"The dotfiles copy was left untouched.",
							display: true,
							attribution: "user",
						},
						{ deliverAs: "nextTurn" },
					);
					return;
				}

				// Stage the removal; the commit drops it from dotfiles. If the
				// skill was never tracked (e.g. its earlier commit failed), there
				// is nothing to remove — a clean no-op, not an error.
				const rm = await bareGit(pi, "rm", "--", repoRelPath);
				if (rm.code !== 0) {
					const isUntracked =
						/did not match any file|fatal: pathspec|untracked/i.test(rm.stderr);
					if (isUntracked) return; // never tracked → nothing to commit
					pi.sendMessage(
						{
							customType: "managed-skill-dotfiles",
							content: `Could not stage removal of managed skill "${name}":\n${rm.stderr.trim()}`,
							display: true,
							attribution: "user",
						},
						{ deliverAs: "nextTurn" },
					);
					return;
				}

				// Commit the removal into dotfiles.
				const commit = await bareGit(pi, "commit", "-m", `Remove managed-skill: ${name}`, "--", repoRelPath);
				if (commit.code !== 0) {
					const detail = (commit.stderr || commit.stdout).trim();
					pi.sendMessage(
						{
							customType: "managed-skill-dotfiles",
							content:
								`managed skill "${name}" was deleted but its dotfiles removal commit was rejected:\n` +
								(detail ? detail : `git commit exited ${commit.code} with no output.`) +
								`\nThe file ${repoRelPath} is staged for removal but NOT committed.`,
							display: true,
							attribution: "user",
						},
						{ deliverAs: "nextTurn" },
					);
					return;
				}

				pi.sendMessage(
					{
						customType: "managed-skill-dotfiles",
						content:
							`Removed managed skill "${name}" from dotfiles (${commit.stdout.trim().split("\n")[0] ?? `commit ${commit.code}`}).`,
						display: true,
						attribution: "user",
					},
					{ deliverAs: "nextTurn" },
				);
				return;
			}

			// --- create / update ---
			if (!onDisk) {
				// Create/update succeeded per the tool result but the file isn't
				// where we expect — refuse to guess a path and add something wrong.
				pi.sendMessage(
					{
						customType: "managed-skill-dotfiles",
						content:
							`manage_skill reported a successful "${action}" for "${name}", but no ` +
							`SKILL.md was found at ${diskPath}. The skill was not auto-added to dotfiles.`,
						display: true,
						attribution: "user",
					},
					{ deliverAs: "nextTurn" },
				);
				return;
			}

			// Stage just this skill (never add -A). add of an already-clean path
			// is a no-op; the staged-diff guard below still returns early.
			const add = await bareGit(pi, "add", "--", repoRelPath);
			if (add.code !== 0) {
				pi.sendMessage(
					{
						customType: "managed-skill-dotfiles",
						content: `Could not stage managed skill "${name}" into dotfiles:\n${add.stderr.trim()}`,
						display: true,
						attribution: "user",
					},
					{ deliverAs: "nextTurn" },
				);
				return;
			}

			// Nothing staged means the file is byte-identical to HEAD — skip the
			// no-op commit and the messaging noise.
			const staged = await bareGit(pi, "diff", "--cached", "--quiet", "--", repoRelPath);
			if (staged.code === 0) return;

			const commit = await bareGit(
				pi,
				"commit",
				"-m",
				// Matches the repo's existing convention, e.g.
				// "Add managed-skill: watermarks-remover-frontmatter-value-false-positive".
				action === "create"
					? `Add managed-skill: ${name}`
					: `Update managed-skill: ${name}`,
				"--",
				repoRelPath,
			);

			if (commit.code !== 0) {
				// Usually the global gitleaks pre-commit hook refusing. Surface the
				// hook's message rather than swallowing it or force-bypassing.
				const detail = (commit.stderr || commit.stdout).trim();
				pi.sendMessage(
					{
						customType: "managed-skill-dotfiles",
						content:
							`managed skill "${name}" was written but its dotfiles commit was rejected:\n` +
							(detail ? detail : `git commit exited ${commit.code} with no output.`) +
							`\nThe skill is saved locally at ${diskPath} but NOT backed up. ` +
							"If this is a gitleaks false positive you can commit it manually with " +
							"`GIT_ALLOW_SECRETS=1`.",
						display: true,
						attribution: "user",
					},
					{ deliverAs: "nextTurn" },
				);
				return;
			}

			pi.sendMessage(
				{
					customType: "managed-skill-dotfiles",
					content:
						`Managed skill "${name}" was auto-committed to dotfiles (${commit.stdout.trim().split("\n")[0] ?? `commit ${commit.code}`}).`,
					display: true,
					attribution: "user",
				},
				{ deliverAs: "nextTurn" },
			);
		} finally {
			inFlight.delete(name);
		}
	}

	pi.on("tool_result", (event) => {
		if (event.toolName !== "manage_skill") return;
		if (event.isError) return; // failed mutation — nothing to back up
		void syncSkillToDotfiles(event.input);
	});
}
