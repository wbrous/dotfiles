// managed-skill-dotfiles: auto-backup newly created/updated managed skills
// (~/.omp/agent/managed-skills/<name>/SKILL.md) into the dotfiles bare repo
// (~/.dotfiles) the moment the agent's `manage_skill` tool lands a successful
// create/update.
//
// Motivation: when omp creates a managed skill via `manage_skill`, it writes
// the skill to disk but does not touch the dotfiles repo, so the new skill is
// left unbacked-up until a manual fan-out scout survey. This extension removes
// that step: create/update is auto-committed with the repo's existing commit
// convention. Deletes are deliberately left alone (removing the dotfiles copy
// on a skill delete is a destructive action that should stay an explicit,
// human-supervised decision).
//
// Mechanism: hook the `tool_result` event (fires after every tool executes with
// { toolName, input, isError }). On a successful `manage_skill` create/update,
// `git add` the skill dir and commit it via pi.exec against the bare repo.
//
// Guardrails:
//   - Never `add -A`; only the single <name>/SKILL.md path.
//   - Skip commits when the file is byte-identical to HEAD (no no-op commit
//     noise in the "what's actually new" signal).
//   - Never bypass the global gitleaks pre-commit hook (GIT_ALLOW_SECRETS=1 is
//     a deliberate human escape hatch). If the commit is blocked, surface the
//     hook's stderr via sendMessage so the agent/user can decide.
//   - De-duplicate in-flight ops per skill name so two rapid create/updates of
//     the same skill can't race the bare-repo commit.
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
 * Marks the git subprocess as agent-driven so the shared `prepare-commit-msg`
 * hook (see the git-scoped-coauthor-trailer skill) appends the
 * `Co-authored-by: wbrous-dev-ai` trailer to the commit. The hook gates on
 * `OMPCODE=1`, which `pi.exec` does not inherit (the harness only injects
 * `OMPCODE` into the per-tool bash env, not the omp process env the extension
 * runs in), so we set it on this process before spawning — Bun child
 * processes inherit `process.env` by default when no `env` option is passed.
 * Setting it here (rather than only at commit time) keeps every git call
 * uniformly marked as agent-driven.
 */
async function bareGit(pi: ExtensionAPI, ...args: string[]): Promise<BareGit> {
	process.env.OMPCODE = "1";
	const result = await pi.exec(
		"git",
		[`--git-dir=${DOTFILES_DIR}`, `--work-tree=${homedir()}`, ...args],
		{ cwd: homedir() },
	);
	return { args, stdout: result.stdout, stderr: result.stderr, code: result.code };
}

export default function managedSkillDotfilesExtension(pi: ExtensionAPI): void {
	/** Guard against overlapping ops for the same skill name. */
	const inFlight = new Set<string>();

	async function syncSkillToDotfiles(input: Record<string, unknown>): Promise<void> {
		const action = input.action;
		const name = input.name;
		if (typeof name !== "string" || !name || (action !== "create" && action !== "update")) {
			return;
		}
		if (!skillExistsOnDisk(name)) {
			// Create succeeded per the tool result but the file isn't where we
			// expect — refuse to guess a path and add something wrong. Report it.
			pi.sendMessage(
				{
					customType: "managed-skill-dotfiles",
					content:
						`manage_skill reported a successful "${action}" for "${name}", but no ` +
						`SKILL.md was found at ${MANAGED_SKILLS_DIR}/${name}. The skill was not auto-added to dotfiles.`,
					display: true,
					attribution: "user",
				},
				{ triggerTurn: true },
			);
			return;
		}

		// If an op for this name is already in flight, let it absorb this one —
		// the running commit will already have staged the latest file content.
		if (inFlight.has(name)) return;
		inFlight.add(name);
		try {
			const repoRelPath = `.omp/agent/managed-skills/${name}/SKILL.md`;

			// Stage just this skill (never add -A). add of an already-clean path
			// is a no-op; the staged-diff guard below still returns early.
			const add = await bareGit(pi, "add", "--", repoRelPath);
			if (add.code !== 0) {
				pi.sendMessage(
					{
						customType: "managed-skill-dotfiles",
						content:
							`Could not stage managed skill "${name}" into dotfiles:\n` +
							`git add -- ${repoRelPath}\n${add.stderr.trim()}`,
						display: true,
						attribution: "user",
					},
					{ triggerTurn: true },
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
							`managed skill "${name}" was created but its dotfiles commit was rejected:\n` +
							(detail ? detail : `git commit exited ${commit.code} with no output.`) +
							`\nThe skill is saved locally at ${MANAGED_SKILLS_DIR}/${name}/SKILL.md but NOT backed up. ` +
							"If this is a gitleaks false positive you can commit it manually with " +
							"`GIT_ALLOW_SECRETS=1`.",
						display: true,
						attribution: "user",
					},
					{ triggerTurn: true },
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
				{ triggerTurn: true },
			);
		} finally {
			inFlight.delete(name);
		}
	}

	pi.on("tool_result", (event) => {
		if (event.toolName !== "manage_skill") return;
		if (event.isError) return; // failed create/update — nothing to back up
		void syncSkillToDotfiles(event.input);
	});
}
