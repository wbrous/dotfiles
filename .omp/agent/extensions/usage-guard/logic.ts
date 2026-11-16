// Pure logic for usage-guard: config validation, command parsing, usage extraction, verdicts.
// No I/O and no omp imports, so everything here is unit-testable.

/** The two subscription windows this extension watches (rolling 5-hour, weekly). */
export const WINDOWS = ["5h", "week"] as const;
export type WindowName = (typeof WINDOWS)[number];

/** Percent-used thresholds for one window. Invariant: 0 < warn < cutoff <= 100. */
export interface Threshold {
	readonly warn: number;
	readonly cutoff: number;
}

export interface Config {
	readonly enabled: boolean;
	readonly thresholds: Readonly<Record<WindowName, Threshold>>;
}

export const DEFAULT_CONFIG: Config = {
	enabled: true,
	thresholds: {
		"5h": { warn: 70, cutoff: 80 },
		week: { warn: 90, cutoff: 93 },
	},
};

/** Fraction used (0..1) per window; a window is absent when Anthropic reported no data for it. */
export type Usage = Partial<Record<WindowName, number>>;

export type Level = "ok" | "warn" | "cutoff";

export interface Verdict {
	readonly level: Level;
	/** Windows at or past the verdict's level, with their percent used. */
	readonly triggered: readonly { window: WindowName; percentUsed: number; threshold: Threshold }[];
}

const WINDOW_LABEL: Record<WindowName, string> = { "5h": "5-hour", week: "weekly" };
export const windowLabel = (w: WindowName): string => WINDOW_LABEL[w];

/**
 * Throws unless 0 < warn < cutoff <= 100 for the given window.
 * @throws Error naming the window and the violated rule.
 */
export function assertThreshold(window: WindowName, t: Threshold): void {
	for (const [k, v] of [["warn", t.warn], ["cutoff", t.cutoff]] as const) {
		if (!Number.isFinite(v) || v <= 0 || v > 100) {
			throw new Error(`${window} ${k} must be a number in (0, 100], got ${v}`);
		}
	}
	if (t.warn >= t.cutoff) {
		throw new Error(`${window} warn (${t.warn}) must be below cutoff (${t.cutoff})`);
	}
}

/**
 * Parses persisted JSON into a Config. Missing fields take defaults.
 * @throws Error when the JSON is malformed or a value violates the threshold invariant.
 */
export function parseConfig(json: string): Config {
	const raw: unknown = JSON.parse(json);
	if (typeof raw !== "object" || raw === null || Array.isArray(raw)) throw new Error("config must be a JSON object");
	const obj = raw as { enabled?: unknown; thresholds?: Record<string, { warn?: unknown; cutoff?: unknown } | undefined> };
	if (obj.enabled !== undefined && typeof obj.enabled !== "boolean") throw new Error("enabled must be a boolean");
	const thresholds = {} as Record<WindowName, Threshold>;
	for (const w of WINDOWS) {
		const given = obj.thresholds?.[w];
		const t: Threshold = {
			warn: (given?.warn as number | undefined) ?? DEFAULT_CONFIG.thresholds[w].warn,
			cutoff: (given?.cutoff as number | undefined) ?? DEFAULT_CONFIG.thresholds[w].cutoff,
		};
		assertThreshold(w, t);
		thresholds[w] = t;
	}
	return { enabled: obj.enabled ?? DEFAULT_CONFIG.enabled, thresholds };
}

export type CommandResult =
	| { readonly kind: "status" }
	| { readonly kind: "update"; readonly config: Config; readonly message: string }
	| { readonly kind: "error"; readonly message: string };

export const USAGE_HELP = [
	"/usage-guard                      show status",
	"/usage-guard on | off             enable / disable",
	"/usage-guard 5h-warn <pct>        5-hour warning threshold",
	"/usage-guard 5h-cutoff <pct>      5-hour hard cutoff",
	"/usage-guard week-warn <pct>      weekly warning threshold",
	"/usage-guard week-cutoff <pct>    weekly hard cutoff",
	"/usage-guard reset                restore defaults (70/80 and 90/93, enabled)",
].join("\n");

const KEY_RE = /^(5h|week)-(warn|cutoff)$/;

/** Parses the argument string of `/usage-guard` against the current config. Never throws. */
export function applyCommand(args: string, current: Config): CommandResult {
	const parts = args.trim().split(/\s+/).filter(Boolean);
	if (parts.length === 0) return { kind: "status" };
	const [head, value, ...extra] = parts;
	const key = head.toLowerCase();

	if (extra.length > 0 || (value !== undefined && !KEY_RE.test(key))) {
		return { kind: "error", message: `Unexpected arguments.\n${USAGE_HELP}` };
	}
	if (key === "on" || key === "off") {
		const enabled = key === "on";
		return { kind: "update", config: { ...current, enabled }, message: `usage-guard ${enabled ? "enabled" : "disabled"}` };
	}
	if (key === "reset") {
		return { kind: "update", config: DEFAULT_CONFIG, message: "usage-guard reset to defaults" };
	}
	const m = KEY_RE.exec(key);
	if (!m) return { kind: "error", message: `Unknown option "${head}".\n${USAGE_HELP}` };
	if (value === undefined) return { kind: "error", message: `${key} needs a percentage.\n${USAGE_HELP}` };

	const pct = Number(value.replace(/%$/, ""));
	const window = m[1] as WindowName;
	const field = m[2] as keyof Threshold;
	const next: Threshold = { ...current.thresholds[window], [field]: pct };
	try {
		assertThreshold(window, next);
	} catch (e) {
		return { kind: "error", message: (e as Error).message };
	}
	return {
		kind: "update",
		config: { ...current, thresholds: { ...current.thresholds, [window]: next } },
		message: `${window} ${field} set to ${pct}%`,
	};
}

/** Structural view of the fields we read from an omp `UsageReport`. */
export interface UsageReportLike {
	readonly provider: string;
	readonly limits: readonly {
		readonly window?: { readonly id: string };
		readonly scope?: { readonly tier?: string };
		readonly amount?: { readonly usedFraction?: number };
	}[];
}

/** omp's normalized window ids for the rolling 5-hour and the weekly limit. */
const WINDOW_ID: Record<WindowName, string> = { "5h": "5h", week: "7d" };

export function isUsageReportArray(value: unknown): value is UsageReportLike[] {
	return (
		Array.isArray(value) &&
		value.every(r => typeof r === "object" && r !== null && typeof r.provider === "string" && Array.isArray(r.limits))
	);
}

/**
 * Mean used fraction per window over every matching limit of every account of `provider`
 * (several pooled accounts, or several matching limits, are averaged). Per-model tiers
 * (`scope.tier` set) are ignored. A window nothing reports on stays absent, so API-key
 * providers, which report no windows, yield `{}`.
 */
export function extractUsage(reports: readonly UsageReportLike[], provider: string): Usage {
	const usage: Usage = {};
	for (const w of WINDOWS) {
		const fractions = reports
			.filter(r => r.provider === provider)
			.flatMap(r => r.limits)
			.filter(l => l.window?.id === WINDOW_ID[w] && l.scope?.tier === undefined)
			.map(l => l.amount?.usedFraction)
			.filter((f): f is number => typeof f === "number" && Number.isFinite(f));
		if (fractions.length > 0) usage[w] = fractions.reduce((a, b) => a + b, 0) / fractions.length;
	}
	return usage;
}

/**
 * Highest severity wins. A window counts when percentUsed >= threshold. Percent comparison is
 * on the unrounded value, so 69.9% is not yet a warning at a 70% threshold.
 */
export function evaluate(usage: Usage, config: Config): Verdict {
	if (!config.enabled) return { level: "ok", triggered: [] };
	const hits = (field: keyof Threshold) =>
		WINDOWS.flatMap(window => {
			const fraction = usage[window];
			const threshold = config.thresholds[window];
			if (fraction === undefined) return [];
			const percentUsed = fraction * 100;
			return percentUsed >= threshold[field] ? [{ window, percentUsed, threshold }] : [];
		});
	const cutoff = hits("cutoff");
	if (cutoff.length > 0) return { level: "cutoff", triggered: cutoff };
	const warn = hits("warn");
	return warn.length > 0 ? { level: "warn", triggered: warn } : { level: "ok", triggered: [] };
}

const pct = (n: number): string => `${Math.round(n * 10) / 10}%`;

/** The mandatory stop directive injected into the model's context while level is "warn". */
export function warningText(verdict: Verdict, provider: string): string {
	const lines = verdict.triggered.map(
		t =>
			`- ${windowLabel(t.window)} usage: ${pct(t.percentUsed)} used (warning at ${pct(t.threshold.warn)}; HARD CUTOFF at ${pct(t.threshold.cutoff)})`,
	);
	return [
		"<usage-guard>",
		`MANDATORY STOP DIRECTIVE. This is an instruction, not a suggestion. The user's ${provider} subscription usage is nearly exhausted:`,
		...lines,
		"",
		"You MUST now:",
		"1. Do NOT start any new task, feature, investigation, refactor, or subtask.",
		"2. Finish only the single step already in flight, then reach the nearest clean stopping point (code compiles, tree consistent, nothing half-edited).",
		"3. Stop making tool calls and give the user a short final summary: what is done, the exact current state, and the precise next steps for a later session.",
		"",
		"Your session WILL BE FORCIBLY CUT OFF when usage reaches the hard cutoff above. Anything unfinished at that point is lost mid-action. Stop at a safe point now.",
		"</usage-guard>",
	].join("\n");
}

/** Shown to the user (and to the model via tool-block reasons) once the hard cutoff is reached. */
export function cutoffText(verdict: Verdict): string {
	const parts = verdict.triggered.map(t => `${windowLabel(t.window)} ${pct(t.percentUsed)} >= cutoff ${pct(t.threshold.cutoff)}`);
	return `usage-guard cutoff reached (${parts.join(", ")}). Run /usage-guard off or raise the cutoff to continue.`;
}

/** One-line status-bar summary, e.g. "5h 62% · wk 41%". */
export function statusLine(usage: Usage, config: Config): string {
	if (!config.enabled) return "usage-guard off";
	const cell = (label: string, w: WindowName) => (usage[w] === undefined ? `${label} ?` : `${label} ${Math.round((usage[w] as number) * 100)}%`);
	return `${cell("5h", "5h")} · ${cell("wk", "week")}`;
}

export function describeConfig(config: Config): string {
	const t = config.thresholds;
	return [
		`usage-guard: ${config.enabled ? "enabled" : "disabled"}`,
		`5-hour: warn ${t["5h"].warn}%, cutoff ${t["5h"].cutoff}%`,
		`weekly: warn ${t.week.warn}%, cutoff ${t.week.cutoff}%`,
	].join("\n");
}

const escapeHtml = (s: string): string =>
	s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * HTML `<form>` for `ctx.ui.formDialog`: one fieldset per window plus a general one, so Tern shows
 * a tab each. `draft` need not be valid (it is the user's last attempt); `summary` is plain text.
 */
export function buildFormHtml(draft: Config, summary: string, error?: string): string {
	const num = (name: string, label: string, value: number) =>
		`<label>${label} <input type="number" name="${name}" value="${value}" min="0.1" max="100" step="any" required></label>`;
	const t = draft.thresholds;
	return [
		"<form>",
		`<p>${escapeHtml(summary)}</p>`,
		error ? `<p>Not saved: ${escapeHtml(error)}</p>` : "",
		"<fieldset><legend>General</legend>",
		`<label><input type="checkbox" name="enabled" value="on"${draft.enabled ? " checked" : ""}> Enabled</label>`,
		"</fieldset>",
		"<fieldset><legend>5-hour window (percent used)</legend>",
		num("5h-warn", "Warn at (%) - model is told to stop", t["5h"].warn),
		num("5h-cutoff", "Hard cutoff at (%) - run is aborted", t["5h"].cutoff),
		"</fieldset>",
		"<fieldset><legend>Weekly window (percent used)</legend>",
		num("week-warn", "Warn at (%) - model is told to stop", t.week.warn),
		num("week-cutoff", "Hard cutoff at (%) - run is aborted", t.week.cutoff),
		"</fieldset>",
		"</form>",
	].join("\n");
}

/** Reads a field as a finite number, or throws naming the field. */
function numberField(data: Readonly<Record<string, unknown>>, name: string): number {
	const v = data[name];
	const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number(v) : Number.NaN;
	if (!Number.isFinite(n)) throw new Error(`${name} must be a number`);
	return n;
}

/**
 * Builds a Config from submitted `formDialog` data (checkbox omitted when unchecked).
 * @throws Error naming the offending field or violated threshold rule.
 */
export function configFromForm(data: Readonly<Record<string, unknown>>): Config {
	const thresholds = {} as Record<WindowName, Threshold>;
	for (const w of WINDOWS) {
		const t: Threshold = { warn: numberField(data, `${w}-warn`), cutoff: numberField(data, `${w}-cutoff`) };
		assertThreshold(w, t);
		thresholds[w] = t;
	}
	return { enabled: data.enabled === "on", thresholds };
}

/**
 * Best-effort draft from submitted data for re-showing a rejected form; unparsable numbers fall
 * back to `fallback` so the form can always be rebuilt.
 */
export function draftFromForm(data: Readonly<Record<string, unknown>>, fallback: Config): Config {
	const pick = (name: string, dflt: number): number => {
		try {
			return numberField(data, name);
		} catch {
			return dflt;
		}
	};
	const t = fallback.thresholds;
	return {
		enabled: data.enabled === "on",
		thresholds: {
			"5h": { warn: pick("5h-warn", t["5h"].warn), cutoff: pick("5h-cutoff", t["5h"].cutoff) },
			week: { warn: pick("week-warn", t.week.warn), cutoff: pick("week-cutoff", t.week.cutoff) },
		},
	};
}
