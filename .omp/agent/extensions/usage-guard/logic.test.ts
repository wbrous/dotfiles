import { describe, expect, test } from "bun:test";
import {
	applyCommand,
	buildFormHtml,
	configFromForm,
	draftFromForm,
	type Config,
	DEFAULT_CONFIG,
	evaluate,
	extractUsage,
	parseConfig,
	warningText,
} from "./logic";

const cfg = (over: Partial<Config> = {}): Config => ({ ...DEFAULT_CONFIG, ...over });

describe("evaluate", () => {
	// If this fails: the 70%/90% defaults warn too early/late, or the boundary is off by one.
	test("warns exactly at the warn threshold, not below", () => {
		expect(evaluate({ "5h": 0.699 }, cfg()).level).toBe("ok");
		expect(evaluate({ "5h": 0.7 }, cfg()).level).toBe("warn");
		expect(evaluate({ week: 0.899 }, cfg()).level).toBe("ok");
		expect(evaluate({ week: 0.9 }, cfg()).level).toBe("warn");
	});

	// If this fails: the hard cut triggers at the wrong percentage per window.
	test("cuts off exactly at the cutoff threshold", () => {
		expect(evaluate({ "5h": 0.8 }, cfg()).level).toBe("cutoff");
		expect(evaluate({ "5h": 0.799 }, cfg()).level).toBe("warn");
		expect(evaluate({ week: 0.93 }, cfg()).level).toBe("cutoff");
		expect(evaluate({ week: 0.929 }, cfg()).level).toBe("warn");
	});

	// If this fails: a weekly warning masks a 5-hour cutoff (or vice versa) and the run is not stopped.
	test("highest severity across windows wins", () => {
		const v = evaluate({ "5h": 0.85, week: 0.91 }, cfg());
		expect(v.level).toBe("cutoff");
		expect(v.triggered.map(t => t.window)).toEqual(["5h"]);
	});

	// If this fails: a disabled guard still blocks/warns the user.
	test("disabled config is always ok", () => {
		expect(evaluate({ "5h": 1, week: 1 }, cfg({ enabled: false })).level).toBe("ok");
	});

	// If this fails: missing data is treated as 0% or crashes instead of being skipped.
	test("missing windows are ignored", () => {
		expect(evaluate({}, cfg()).level).toBe("ok");
	});
});

describe("applyCommand", () => {
	// If this fails: tuning a threshold does not change the value, or touches the wrong window/field.
	test("sets one field and leaves the others", () => {
		const r = applyCommand("5h-warn 60", DEFAULT_CONFIG);
		if (r.kind !== "update") throw new Error("expected update");
		expect(r.config.thresholds["5h"]).toEqual({ warn: 60, cutoff: 80 });
		expect(r.config.thresholds.week).toEqual({ warn: 90, cutoff: 93 });
	});

	// If this fails: "%" suffix input like "75%" is rejected or parsed as NaN.
	test("accepts a trailing percent sign", () => {
		const r = applyCommand("week-cutoff 95%", DEFAULT_CONFIG);
		if (r.kind !== "update") throw new Error("expected update");
		expect(r.config.thresholds.week.cutoff).toBe(95);
	});

	// If this fails: invalid thresholds (warn >= cutoff, <=0, >100, NaN) get persisted.
	test.each([
		"5h-warn 80",
		"5h-warn 90",
		"5h-cutoff 70",
		"5h-warn 0",
		"5h-warn -5",
		"week-cutoff 101",
		"week-cutoff abc",
		"week-cutoff NaN",
		"week-cutoff",
	])("rejects %s", args => {
		expect(applyCommand(args, DEFAULT_CONFIG).kind).toBe("error");
	});

	// If this fails: 100 (the max valid cutoff) is rejected.
	test("accepts cutoff of exactly 100", () => {
		expect(applyCommand("week-cutoff 100", DEFAULT_CONFIG).kind).toBe("update");
	});

	// If this fails: on/off/reset do not toggle enabled state or restore defaults.
	test("on, off, reset", () => {
		const off = applyCommand("off", DEFAULT_CONFIG);
		if (off.kind !== "update") throw new Error("expected update");
		expect(off.config.enabled).toBe(false);
		const on = applyCommand("on", off.config);
		if (on.kind !== "update") throw new Error("expected update");
		expect(on.config.enabled).toBe(true);
		const tuned = applyCommand("5h-warn 10", DEFAULT_CONFIG);
		if (tuned.kind !== "update") throw new Error("expected update");
		const reset = applyCommand("reset", tuned.config);
		if (reset.kind !== "update") throw new Error("expected update");
		expect(reset.config).toEqual(DEFAULT_CONFIG);
	});

	// If this fails: empty args don't show status, or junk args are silently accepted.
	test("empty is status; unknown and extra args are errors", () => {
		expect(applyCommand("  ", DEFAULT_CONFIG).kind).toBe("status");
		expect(applyCommand("bogus", DEFAULT_CONFIG).kind).toBe("error");
		expect(applyCommand("on 5", DEFAULT_CONFIG).kind).toBe("error");
		expect(applyCommand("5h-warn 1 2", DEFAULT_CONFIG).kind).toBe("error");
	});
});

describe("config persistence", () => {
	// If this fails: saved config does not roundtrip through parseConfig.
	test("roundtrips", () => {
		const r = applyCommand("5h-cutoff 85", DEFAULT_CONFIG);
		if (r.kind !== "update") throw new Error("expected update");
		expect(parseConfig(JSON.stringify(r.config))).toEqual(r.config);
	});

	// If this fails: a hand-edited bad file is silently accepted instead of surfaced.
	test("rejects invalid persisted thresholds and non-objects", () => {
		expect(() => parseConfig('{"thresholds":{"5h":{"warn":90,"cutoff":80}}}')).toThrow();
		expect(() => parseConfig("[]")).toThrow();
		expect(() => parseConfig('{"enabled":"yes"}')).toThrow();
	});

	// If this fails: partial files lose defaults for unspecified windows.
	test("fills missing fields from defaults", () => {
		expect(parseConfig("{}")).toEqual(DEFAULT_CONFIG);
	});
});

describe("extractUsage", () => {
	const limit = (windowId: string, f: number, tier?: string) => ({
		window: { id: windowId },
		scope: tier === undefined ? {} : { tier },
		amount: { usedFraction: f },
	});
	const report = (provider: string, five: number, week: number) => ({
		provider,
		limits: [limit("5h", five), limit("7d", week), limit("7d", 0.99, "opus"), limit("monthly", 0.5)],
	});

	// If this fails: per-model tiers or monthly windows leak into the 5h/weekly numbers and trigger early stops.
	test("reads only untiered 5h and 7d limits", () => {
		expect(extractUsage([report("anthropic", 0.2, 0.3)], "anthropic")).toEqual({ "5h": 0.2, week: 0.3 });
	});

	// If this fails: pooled accounts are not averaged (max/first/sum used instead).
	test("averages across accounts of the same provider and ignores other providers", () => {
		const usage = extractUsage(
			[report("anthropic", 0.2, 0.3), report("anthropic", 0.6, 0.1), report("openai", 0.99, 0.99)],
			"anthropic",
		);
		expect(usage["5h"]).toBeCloseTo(0.4);
		expect(usage.week).toBeCloseTo(0.2);
	});

	// If this fails: absent windows (API-key providers) turn into 0 and mask missing data, or crash.
	test("providers without windows yield empty usage", () => {
		expect(extractUsage([{ provider: "anthropic", limits: [] }], "anthropic")).toEqual({});
		expect(extractUsage([], "anthropic")).toEqual({});
	});

	// If this fails: a provider with only a 5h window gets a bogus weekly value.
	test("windows are independent", () => {
		expect(extractUsage([{ provider: "p", limits: [limit("5h", 0.5)] }], "p")).toEqual({ "5h": 0.5 });
	});
});


describe("warningText", () => {
	// If this fails: the model is not told the actual cutoff, or the text reads as a mere recommendation.
	test("states mandatory stop and the real cutoff percentages", () => {
		const text = warningText(evaluate({ "5h": 0.72, week: 0.91 }, DEFAULT_CONFIG), "opencode-go");
		expect(text).toContain("opencode-go");
		expect(text).toContain("MANDATORY");
		expect(text).toContain("FORCIBLY CUT OFF");
		expect(text).toContain("HARD CUTOFF at 80%");
		expect(text).toContain("HARD CUTOFF at 93%");
	});
});

describe("form", () => {
	const data = (over: Record<string, unknown> = {}) => ({
		enabled: "on",
		"5h-warn": 65,
		"5h-cutoff": 75,
		"week-warn": 85,
		"week-cutoff": 92,
		...over,
	});

	// If this fails: submitted form values are not turned into the saved config (wrong field mapping).
	test("maps submitted data to a config", () => {
		expect(configFromForm(data())).toEqual({
			enabled: true,
			thresholds: { "5h": { warn: 65, cutoff: 75 }, week: { warn: 85, cutoff: 92 } },
		});
	});

	// If this fails: unchecking Enabled (checkbox omitted from data) does not disable the guard.
	test("omitted checkbox means disabled", () => {
		const { enabled: _omit, ...rest } = data();
		expect(configFromForm(rest).enabled).toBe(false);
	});

	// If this fails: bad form input (order, range, non-number, missing) is persisted.
	test.each([
		{ "5h-warn": 80 },
		{ "week-cutoff": 101 },
		{ "5h-cutoff": "abc" },
		{ "week-warn": undefined },
		{ "5h-warn": 0 },
	])("rejects invalid form data %j", over => {
		expect(() => configFromForm(data(over))).toThrow();
	});

	// If this fails: the rejected-form redraw loses what the user typed or crashes on junk.
	test("draft keeps parsable values and falls back otherwise", () => {
		const draft = draftFromForm(data({ "5h-warn": 99, "week-warn": "x" }), DEFAULT_CONFIG);
		expect(draft.thresholds["5h"].warn).toBe(99);
		expect(draft.thresholds.week.warn).toBe(90);
	});

	// If this fails: the form does not show current values, or user text can inject markup.
	test("html prefills values, checks Enabled, escapes text", () => {
		const html = buildFormHtml(DEFAULT_CONFIG, "x <b>&</b>", 'bad "x"');
		expect(html).toContain('name="5h-warn" value="70"');
		expect(html).toContain('name="week-cutoff" value="93"');
		expect(html).toContain("checked");
		expect(html).toContain("x &lt;b&gt;&amp;&lt;/b&gt;");
		expect(html).toContain("bad &quot;x&quot;");
		expect(buildFormHtml({ ...DEFAULT_CONFIG, enabled: false }, "")).not.toContain("checked");
	});
});
