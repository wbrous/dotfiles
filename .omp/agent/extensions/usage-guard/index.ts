// usage-guard: when the active model's provider subscription is close to its 5-hour / weekly
// limit, force the model to wrap up (mandatory stop directive in its context), then hard-cut the
// run at the cutoff. Works for any provider that reports usage windows (API-key providers report
// none and are left alone). Tune with /usage-guard.
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import {
	buildFormHtml,
	configFromForm,
	draftFromForm,
	applyCommand,
	type Config,
	cutoffText,
	DEFAULT_CONFIG,
	describeConfig,
	evaluate,
	extractUsage,
	isUsageReportArray,
	parseConfig,
	statusLine,
	type Usage,
	USAGE_HELP,
	type Verdict,
	warningText,
} from "./logic";

const CONFIG_PATH = join(process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".omp", "agent"), "usage-guard.json");
/** Minimum gap between usage lookups per provider; omp additionally caches reports for ~5 minutes. */
const REFRESH_MS = 30_000;
const MESSAGE_TYPE = "usage-guard";
const OK: Verdict = { level: "ok", triggered: [] };

async function loadConfig(): Promise<Config> {
	let text: string;
	try {
		text = await readFile(CONFIG_PATH, "utf8");
	} catch (e) {
		if ((e as NodeJS.ErrnoException).code === "ENOENT") return DEFAULT_CONFIG;
		throw e;
	}
	return parseConfig(text);
}

async function saveConfig(config: Config): Promise<void> {
	await mkdir(dirname(CONFIG_PATH), { recursive: true });
	const tmp = `${CONFIG_PATH}.${process.pid}.tmp`;
	await writeFile(tmp, `${JSON.stringify(config, null, 2)}\n`);
	await rename(tmp, CONFIG_PATH);
}

interface ProviderUsage {
	usage: Usage;
	fetchedAt: number;
}

export default function usageGuard(pi: ExtensionAPI) {
	let config: Config = DEFAULT_CONFIG;
	const cache = new Map<string, ProviderUsage>();
	const lastFetchError = new Map<string, string>();
	let lastLevel: Verdict["level"] = "ok";

	/**
	 * Mean usage windows for `provider` (throttled). Providers with no usage windows (API keys)
	 * yield `{}`. Fetch errors are surfaced once per distinct message; last known usage is kept.
	 */
	async function usageFor(ctx: ExtensionContext, provider: string, force = false): Promise<Usage> {
		const cached = cache.get(provider);
		if (!force && cached && Date.now() - cached.fetchedAt < REFRESH_MS) return cached.usage;
		let usage: Usage = cached?.usage ?? {};
		try {
			const reports = await ctx.modelRegistry.authStorage.usage.reports({ provider });
			if (reports !== null && reports !== undefined) {
				if (!isUsageReportArray(reports)) throw new Error("unexpected usage report shape");
				usage = extractUsage(reports, provider);
			}
			lastFetchError.delete(provider);
		} catch (e) {
			const message = e instanceof Error ? e.message : String(e);
			if (lastFetchError.get(provider) !== message && ctx.agent.kind === "main") {
				ctx.ui.notify(`usage-guard: could not read ${provider} usage: ${message}`, "warning");
			}
			lastFetchError.set(provider, message);
		}
		cache.set(provider, { usage, fetchedAt: Date.now() });
		return usage;
	}

	function paintStatus(ctx: ExtensionContext, usage: Usage): void {
		if (ctx.agent.kind !== "main") return;
		const hasData = Object.keys(usage).length > 0;
		ctx.ui.setStatus("usage-guard", !config.enabled || hasData ? statusLine(usage, config) : undefined);
	}

	/** Verdict for the current model's provider, or "ok" when disabled / no usage windows exist. */
	async function check(ctx: ExtensionContext): Promise<Verdict> {
		const provider = ctx.model?.provider;
		if (!config.enabled || provider === undefined) return OK;
		const usage = await usageFor(ctx, provider);
		paintStatus(ctx, usage);
		const verdict = evaluate(usage, config);
		if (verdict.level !== lastLevel && ctx.agent.kind === "main") {
			if (verdict.level === "warn") ctx.ui.notify("usage-guard: warning threshold reached; the model was told to wrap up.", "warning");
			if (verdict.level === "cutoff") ctx.ui.notify(cutoffText(verdict), "error");
		}
		lastLevel = verdict.level;
		return verdict;
	}

	pi.on("session_start", async (_event, ctx) => {
		try {
			config = await loadConfig();
		} catch (e) {
			config = DEFAULT_CONFIG;
			ctx.ui.notify(`usage-guard: ignoring invalid ${CONFIG_PATH}: ${(e as Error).message}. Using defaults.`, "error");
		}
		if (ctx.model) paintStatus(ctx, await usageFor(ctx, ctx.model.provider, true));
	});

	// Runs before every LLM request, including mid-run tool loops, so crossing a threshold takes
	// effect on the very next request rather than the next user prompt.
	pi.on("context", async (event, ctx) => {
		const verdict = await check(ctx);
		if (verdict.level === "cutoff") {
			ctx.abort();
			return;
		}
		if (verdict.level !== "warn" || ctx.model === undefined) return;
		return {
			messages: [
				...event.messages,
				{
					role: "custom",
					customType: MESSAGE_TYPE,
					content: warningText(verdict, ctx.model.provider),
					display: false,
					attribution: "user",
					timestamp: Date.now(),
				},
			],
		};
	});

	// Safety net: if an abort is still draining, no further tool may start past the cutoff.
	pi.on("tool_call", async (_event, ctx) => {
		const verdict = await check(ctx);
		if (verdict.level === "cutoff") return { block: true, reason: cutoffText(verdict) };
	});

	// The form re-opens with the user's own values and the reason until it is valid or cancelled.
	async function editInForm(ctx: ExtensionContext, current: string): Promise<void> {
		let draft = config;
		let error: string | undefined;
		for (;;) {
			const answer = await ctx.ui.formDialog?.(buildFormHtml(draft, current, error));
			if (!answer) return;
			let next: Config;
			try {
				next = configFromForm(answer.data);
			} catch (e) {
				error = e instanceof Error ? e.message : String(e);
				draft = draftFromForm(answer.data, config);
				continue;
			}
			await saveConfig(next);
			config = next;
			lastLevel = "ok";
			ctx.ui.notify("usage-guard settings saved", "info");
			return;
		}
	}

	pi.registerCommand("usage-guard", {
		description: "Tune/enable/disable the provider usage stop-guard (5h and weekly warn/cutoff %)",
		getArgumentCompletions: prefix => {
			const options = ["on", "off", "reset", "5h-warn", "5h-cutoff", "week-warn", "week-cutoff"];
			const hits = options.filter(o => o.startsWith(prefix.trim().toLowerCase()));
			return hits.length > 0 ? hits.map(o => ({ value: o, label: o })) : null;
		},
		handler: async (args, ctx) => {
			const result = applyCommand(args, config);
			if (result.kind === "error") {
				ctx.ui.notify(result.message, "error");
				return;
			}
			if (result.kind === "update") {
				await saveConfig(result.config);
				config = result.config;
				lastLevel = "ok";
				ctx.ui.notify(result.message, "info");
			}
			const provider = ctx.model?.provider;
			const usage = provider ? await usageFor(ctx, provider, true) : {};
			paintStatus(ctx, usage);
			const note = provider === undefined ? " (no active model)" : Object.keys(usage).length === 0 ? " (no usage windows reported, e.g. API key: guard inactive)" : "";
			const current = `Current usage (${provider ?? "-"}): ${statusLine(usage, config)}${note}`;
			if (result.kind === "status" && ctx.ui.formDialog) {
				await editInForm(ctx, current);
				return;
			}
			ctx.ui.notify(`${describeConfig(config)}\n${current}\n\n${USAGE_HELP}`, "info");
		},
	});
}
