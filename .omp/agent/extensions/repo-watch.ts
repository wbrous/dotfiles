// repo-watch: subscribe to GitHub issues/PRs and GitLab issues/MRs, get a
// steered update in-session when someone comments, reviews, changes status,
// or merges. Polls via the `gh` / `glab` CLIs (reuses their existing auth —
// no tokens handled by this extension).
//
// Tools: watch_subscribe, watch_unsubscribe, watch_list.
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";
import type { ZodLikeSchema } from "@oh-my-pi/omptype/zod";

// No hardcoded default host: gitlab (and github, redundantly) are inferred
// from the cwd's `git remote get-url origin` when not given explicitly.

const POLL_TICK_MS = 15_000;
const MIN_INTERVAL_SEC = 20;
const DEFAULT_INTERVAL_SEC = 60;
const ALL_EVENTS = ["comment", "review", "status", "merge"] as const;
type WatchEvent = (typeof ALL_EVENTS)[number];

type Platform = "github" | "gitlab";
type Kind = "issue" | "pr"; // "pr" also covers a GitLab merge request
interface RepoRef {
  platform: Platform;
  host: string;
  owner: string;
  repo: string;
}

interface Subscription {
  id: string;
  platform: Platform;
  host: string;
  owner: string; // github: org/user. gitlab: namespace path (may contain slashes)
  repo: string;
  number: number;
  kind: Kind;
  intervalSec: number;
  events: WatchEvent[];
  createdAt: string;
}

interface PollState {
  baseline: boolean; // true until the first snapshot has been captured
  lastCommentIds: Set<number>;
  lastReviewIds: Set<number>;
  state: string | null;
  merged: boolean | null;
  nextDueAt: number;
  lastPolledAt: number | null;
  lastError: string | null;
  lastTitle: string | null;
  lastUrl: string | null;
}

interface Snapshot {
  state: string;
  merged: boolean | null;
  title: string;
  url: string;
  comments: Array<{ id: number; author: string; body: string }>;
  reviews: Array<{ id: number; author: string; state: string; body: string }>;
}

interface GhIssueMeta {
  state: string;
  title: string;
  html_url: string;
}
interface GhPullMeta {
  merged?: boolean | null;
}
interface GhComment {
  id: number;
  user?: { login: string } | null;
  body?: string | null;
}
interface GhReview {
  id: number;
  user?: { login: string } | null;
  state: string;
  body?: string | null;
}
interface GlMeta {
  state: string;
  title: string;
  web_url: string;
}
interface GlNote {
  id: number;
  system?: boolean | null;
  author?: { username: string } | null;
  body?: string | null;
}
type PersistedOp = { op: "add"; sub: Subscription } | { op: "remove"; sub: { id: string } };

interface Schemas {
  ghIssueMeta: ZodLikeSchema<GhIssueMeta>;
  ghPullMeta: ZodLikeSchema<GhPullMeta>;
  ghComments: ZodLikeSchema<GhComment[]>;
  ghReviews: ZodLikeSchema<GhReview[]>;
  glMeta: ZodLikeSchema<GlMeta>;
  glNotes: ZodLikeSchema<GlNote[]>;
  persistedOp: ZodLikeSchema<PersistedOp>;
}

type ZodModule = ExtensionAPI["zod"];

function buildSchemas(zodModule: ZodModule): Schemas {
  const { z } = zodModule;
  const ghUser = z.object({ login: z.string() }).nullable().optional();
  const ghIssueMeta = z.object({ state: z.string(), title: z.string(), html_url: z.string() });
  const ghPullMeta = z.object({ merged: z.boolean().nullable().optional() });
  const ghComments = z.array(z.object({ id: z.number(), user: ghUser, body: z.string().nullable().optional() }));
  const ghReviews = z.array(
    z.object({ id: z.number(), user: ghUser, state: z.string(), body: z.string().nullable().optional() }),
  );
  const glUser = z.object({ username: z.string() }).nullable().optional();
  const glMeta = z.object({ state: z.string(), title: z.string(), web_url: z.string() });
  const glNotes = z.array(
    z.object({ id: z.number(), system: z.boolean().nullable().optional(), author: glUser, body: z.string().nullable().optional() }),
  );
  const subscription = z.object({
    id: z.string(),
    platform: z.enum(["github", "gitlab"]),
    host: z.string(),
    owner: z.string(),
    repo: z.string(),
    number: z.number(),
    kind: z.enum(["issue", "pr"]),
    intervalSec: z.number(),
    events: z.array(z.enum(ALL_EVENTS)),
    createdAt: z.string(),
  });
  const persistedOp = z.union([
    z.object({ op: z.literal("add"), sub: subscription }),
    z.object({ op: z.literal("remove"), sub: z.object({ id: z.string() }) }),
  ]);
  return { ghIssueMeta, ghPullMeta, ghComments, ghReviews, glMeta, glNotes, persistedOp };
}

interface Deps {
  pi: ExtensionAPI;
  schemas: Schemas;
}

// Module-scoped: extensions run in-process for the session's lifetime.
const subs = new Map<string, Subscription>();
const pollStates = new Map<string, PollState>();
let timerHandle: Timer | null = null;

function subId(s: Pick<Subscription, "platform" | "host" | "owner" | "repo" | "number">): string {
  return `${s.platform}:${s.host}:${s.owner}/${s.repo}#${s.number}`;
}

function freshPollState(): PollState {
  return {
    baseline: true,
    lastCommentIds: new Set(),
    lastReviewIds: new Set(),
    state: null,
    merged: null,
    nextDueAt: 0,
    lastPolledAt: null,
    lastError: null,
    lastTitle: null,
    lastUrl: null,
  };
}

function truncate(text: string | null | undefined, n = 240): string {
  const t = (text ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n)}…` : t || "(no body)";
}

function withPerPage(path: string): string {
  return path + (path.includes("?") ? "&" : "?") + "per_page=100";
}

function parseTargetUrl(url: string): (RepoRef & { number: number; kind: Kind }) | null {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  const host = u.hostname.toLowerCase();
  if (host === "github.com" || host === "www.github.com") {
    const m = u.pathname.match(/^\/([^/]+)\/([^/]+)\/(issues|pull)\/(\d+)/);
    if (!m) return null;
    return {
      platform: "github",
      host: "github.com",
      owner: m[1],
      repo: m[2],
      number: Number(m[4]),
      kind: m[3] === "pull" ? "pr" : "issue",
    };
  }
  const m = u.pathname.match(/^\/(.+)\/-\/(issues|merge_requests)\/(\d+)/);
  if (!m) return null;
  const parts = m[1].split("/").filter(Boolean);
  const repo = parts.pop();
  if (!repo || parts.length === 0) return null;
  return {
    platform: "gitlab",
    host: u.hostname,
    owner: parts.join("/"),
    repo,
    number: Number(m[3]),
    kind: m[2] === "merge_requests" ? "pr" : "issue",
  };
}

// Parses `git remote get-url origin` output — https, ssh://, and scp-style
// (`git@host:owner/repo.git`) forms, with or without a `.git` suffix.
// Nested GitLab group paths (`group/subgroup/repo`) are preserved as `owner`.
function parseGitRemoteUrl(remote: string): { host: string; owner: string; repo: string } | null {
  const trimmed = remote.trim().replace(/\.git$/, "");
  let host: string;
  let pathPart: string;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) {
    let u: URL;
    try {
      u = new URL(trimmed);
    } catch {
      return null;
    }
    host = u.hostname;
    pathPart = u.pathname.replace(/^\//, "");
  } else {
    const scpMatch = trimmed.match(/^(?:[\w.-]+@)?([^:/]+):(.+)$/);
    if (!scpMatch) return null;
    host = scpMatch[1];
    pathPart = scpMatch[2];
  }
  const parts = pathPart.split("/").filter(Boolean);
  const repo = parts.pop();
  if (!repo || parts.length === 0) return null;
  return { host, owner: parts.join("/"), repo };
}

// Infers the target repo from the cwd's `git remote get-url origin`. Platform
// is a heuristic: github.com is unambiguous, anything else is assumed to be
// a (self-hosted) GitLab instance — pass `platform`/`host` explicitly to
// override (e.g. a GitHub Enterprise host).
async function inferRepoFromCwd(pi: ExtensionAPI, cwd: string): Promise<RepoRef | null> {
  const result = await pi.exec("git", ["remote", "get-url", "origin"], { cwd });
  if (result.code !== 0) return null;
  const parsed = parseGitRemoteUrl(result.stdout);
  if (!parsed) return null;
  const host = parsed.host.toLowerCase();
  return { platform: host === "github.com" ? "github" : "gitlab", host, owner: parsed.owner, repo: parsed.repo };
}

// Looks up the PR/MR open for the current branch, so `watch_subscribe` can
// run with no `number` inside a checked-out feature branch.
async function detectCurrentPr(pi: ExtensionAPI, cwd: string, ref: RepoRef): Promise<number | null> {
  if (ref.platform === "github") {
    const result = await pi.exec("gh", ["pr", "view", "--json", "number", "-q", ".number"], { cwd });
    const n = Number(result.stdout.trim());
    return result.code === 0 && Number.isFinite(n) && n > 0 ? n : null;
  }
  const result = await pi.exec("glab", ["mr", "view", "--output", "json"], { cwd });
  if (result.code !== 0) return null;
  try {
    const parsed = JSON.parse(result.stdout) as { iid?: number };
    return typeof parsed.iid === "number" && parsed.iid > 0 ? parsed.iid : null;
  } catch {
    return null;
  }
}

// Runs `cmd api <path>`, parses stdout as JSON. Returns null on 404 (missing
// target) so callers can treat "not found" distinctly from a real failure.
async function runApiCli(pi: ExtensionAPI, cmd: "gh" | "glab", host: string, path: string, signal?: AbortSignal): Promise<unknown> {
  const result = await pi.exec(cmd, ["api", withPerPage(path), "--hostname", host], signal ? { signal } : {});
  if (result.code !== 0) {
    const msg = (result.stderr || result.stdout || "").trim();
    if (/\b404\b/.test(msg) || /not found/i.test(msg)) return null;
    throw new Error(`${cmd} api ${path} failed: ${msg || `exit ${result.code}`}`);
  }
  const text = result.stdout.trim();
  return text ? JSON.parse(text) : null;
}

async function fetchGithubSnapshot(deps: Deps, sub: Subscription, signal?: AbortSignal): Promise<Snapshot | null> {
  const { pi, schemas } = deps;
  const base = `repos/${sub.owner}/${sub.repo}`;
  const rawMeta = await runApiCli(pi, "gh", sub.host, `${base}/issues/${sub.number}`, signal);
  if (rawMeta === null) return null;
  const meta = schemas.ghIssueMeta.parse(rawMeta);

  let merged: boolean | null = null;
  if (sub.kind === "pr") {
    const rawPull = await runApiCli(pi, "gh", sub.host, `${base}/pulls/${sub.number}`, signal);
    merged = rawPull === null ? null : Boolean(schemas.ghPullMeta.parse(rawPull).merged);
  }

  const rawComments = await runApiCli(pi, "gh", sub.host, `${base}/issues/${sub.number}/comments`, signal);
  const comments = rawComments === null ? [] : schemas.ghComments.parse(rawComments);

  let reviews: Array<{ id: number; author: string; state: string; body: string }> = [];
  if (sub.kind === "pr") {
    const rawReviews = await runApiCli(pi, "gh", sub.host, `${base}/pulls/${sub.number}/reviews`, signal);
    const parsedReviews = rawReviews === null ? [] : schemas.ghReviews.parse(rawReviews);
    reviews = parsedReviews
      .filter((r) => r.state !== "PENDING")
      .map((r) => ({ id: r.id, author: r.user?.login ?? "unknown", state: r.state, body: r.body ?? "" }));
  }

  return {
    state: meta.state,
    merged,
    title: meta.title,
    url: meta.html_url,
    comments: comments.map((c) => ({ id: c.id, author: c.user?.login ?? "unknown", body: c.body ?? "" })),
    reviews,
  };
}

async function fetchGitlabSnapshot(deps: Deps, sub: Subscription, signal?: AbortSignal): Promise<Snapshot | null> {
  const { pi, schemas } = deps;
  const projId = encodeURIComponent(`${sub.owner}/${sub.repo}`);
  const kindSeg = sub.kind === "pr" ? "merge_requests" : "issues";
  const base = `projects/${projId}/${kindSeg}/${sub.number}`;
  const rawMeta = await runApiCli(pi, "glab", sub.host, base, signal);
  if (rawMeta === null) return null;
  const meta = schemas.glMeta.parse(rawMeta);

  const rawNotes = await runApiCli(pi, "glab", sub.host, `${base}/notes?order_by=created_at&sort=asc`, signal);
  const notes = rawNotes === null ? [] : schemas.glNotes.parse(rawNotes);

  return {
    state: meta.state,
    merged: sub.kind === "pr" ? meta.state === "merged" : null,
    title: meta.title,
    url: meta.web_url,
    comments: notes
      .filter((n) => !n.system)
      .map((n) => ({ id: n.id, author: n.author?.username ?? "unknown", body: n.body ?? "" })),
    reviews: [],
  };
}

function diffSnapshot(ps: PollState, snap: Snapshot, events: WatchEvent[]): string[] {
  const lines: string[] = [];
  const isBaseline = ps.baseline;

  const newComments = snap.comments.filter((c) => !ps.lastCommentIds.has(c.id));
  const newReviews = snap.reviews.filter((r) => !ps.lastReviewIds.has(r.id));

  if (!isBaseline) {
    if (events.includes("comment")) {
      for (const c of newComments) lines.push(`${c.author} commented: ${truncate(c.body)}`);
    }
    if (events.includes("review")) {
      for (const r of newReviews) lines.push(`${r.author} reviewed (${r.state}): ${truncate(r.body)}`);
    }
    if (events.includes("status") && ps.state !== null && ps.state !== snap.state) {
      lines.push(`status changed: ${ps.state} -> ${snap.state}`);
    }
    if (events.includes("merge") && ps.merged === false && snap.merged === true) {
      lines.push(`merged`);
    }
  }

  ps.baseline = false;
  ps.lastCommentIds = new Set(snap.comments.map((c) => c.id));
  ps.lastReviewIds = new Set(snap.reviews.map((r) => r.id));
  ps.state = snap.state;
  ps.merged = snap.merged;
  ps.lastTitle = snap.title;
  ps.lastUrl = snap.url;

  return lines;
}

function labelFor(sub: Subscription): string {
  const kindWord = sub.kind === "pr" ? (sub.platform === "github" ? "PR" : "MR") : "issue";
  return `${sub.platform === "github" ? "GitHub" : "GitLab"} ${kindWord} ${sub.owner}/${sub.repo}#${sub.number}`;
}

async function pollOne(deps: Deps, ctx: ExtensionContext, sub: Subscription): Promise<void> {
  const ps = pollStates.get(sub.id);
  if (!ps) return;
  try {
    const snap = sub.platform === "github" ? await fetchGithubSnapshot(deps, sub) : await fetchGitlabSnapshot(deps, sub);
    ps.lastPolledAt = Date.now();
    ps.lastError = null;
    if (!snap) {
      ps.lastError = "not found (deleted, renamed, or inaccessible)";
      return;
    }
    const lines = diffSnapshot(ps, snap, sub.events);
    if (lines.length === 0) return;

    const digest = [`Update on ${labelFor(sub)} - "${snap.title}"`, ...lines.map((l) => `- ${l}`), snap.url].join(
      "\n",
    );

    ctx.ui.notify(`${labelFor(sub)}: ${lines.length} update(s)`, "info");
    deps.pi.sendMessage(
      { customType: "repo-watch-update", content: digest, display: true, attribution: "user" },
      { deliverAs: "steer", triggerTurn: true },
    );
  } catch (err) {
    ps.lastError = err instanceof Error ? err.message : String(err);
    deps.pi.logger.warn(`repo-watch: poll failed for ${sub.id}: ${ps.lastError}`);
  }
}

async function pollTick(deps: Deps, ctx: ExtensionContext): Promise<void> {
  const now = Date.now();
  for (const sub of subs.values()) {
    const ps = pollStates.get(sub.id);
    if (!ps || now < ps.nextDueAt) continue;
    ps.nextDueAt = now + sub.intervalSec * 1000;
    await pollOne(deps, ctx, sub);
  }
}

function persist(pi: ExtensionAPI, op: "add" | "remove", sub: Subscription | { id: string }): void {
  pi.appendEntry("repo-watch-sub", { op, sub });
}

function rebuildFromBranch(deps: Deps, ctx: ExtensionContext): void {
  subs.clear();
  pollStates.clear();
  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type !== "custom" || entry.customType !== "repo-watch-sub") continue;
    const parsed = deps.schemas.persistedOp.safeParse(entry.data);
    if (!parsed.success) continue;
    if (parsed.data.op === "add") {
      subs.set(parsed.data.sub.id, parsed.data.sub);
      pollStates.set(parsed.data.sub.id, freshPollState());
    } else {
      subs.delete(parsed.data.sub.id);
      pollStates.delete(parsed.data.sub.id);
    }
  }
}

export default function (pi: ExtensionAPI) {
  const { z } = pi.zod;
  const schemas = buildSchemas(pi.zod);
  const deps: Deps = { pi, schemas };

  pi.setLabel("Repo Watch (GitHub/GitLab)");

  pi.on("session_start", async (_event, ctx) => {
    rebuildFromBranch(deps, ctx);
    if (!timerHandle) {
      timerHandle = ctx.setInterval(() => pollTick(deps, ctx), POLL_TICK_MS);
    }
  });

  pi.on("session_branch", async (_event, ctx) => rebuildFromBranch(deps, ctx));
  pi.on("session_tree", async (_event, ctx) => rebuildFromBranch(deps, ctx));

  pi.on("session_shutdown", async (_event, ctx) => {
    if (timerHandle) {
      ctx.clearTimer(timerHandle);
      timerHandle = null;
    }
  });

  pi.registerTool({
    name: "watch_subscribe",
    label: "Watch Issue/PR/MR",
    description:
      "Subscribe to a GitHub issue/PR or GitLab issue/MR. Polls in the background and pushes an " +
      "in-session update (comment, review, status change, merge) as it happens — no need to poll " +
      'manually. `kind: "pr"` covers both GitHub PRs and GitLab MRs. Repo/host default to the cwd\'s ' +
      "`git remote get-url origin` when `url`/`owner`/`repo` are omitted; `number` defaults to the " +
      "current branch's open PR/MR when omitted (via `gh pr view` / `glab mr view`). So inside a repo " +
      "with an open PR for the current branch, calling this with no arguments watches that PR. " +
      "Otherwise give `url`, or `owner`/`repo`/`number`/`kind` (with `platform`/`host` to override the " +
      "inferred git remote). Calling this again for the same target updates its interval/events " +
      "instead of duplicating it.",
    parameters: z.object({
      url: z.string().optional().describe("Full web URL, e.g. https://github.com/org/repo/pull/42"),
      platform: z.enum(["github", "gitlab"]).optional().describe("Overrides the platform inferred from the git remote host"),
      host: z.string().optional().describe("Overrides the host inferred from the cwd's git remote origin"),
      owner: z
        .string()
        .optional()
        .describe("org/user (github) or full namespace path (gitlab). Default: inferred from cwd's git remote origin"),
      repo: z.string().optional().describe("Default: inferred from cwd's git remote origin"),
      number: z
        .number()
        .int()
        .positive()
        .optional()
        .describe("Issue/PR number, or MR iid on gitlab. Default: current branch's open PR/MR"),
      kind: z.enum(["issue", "pr"]).optional().describe('Default: "pr" when a current-branch PR/MR is found'),
      intervalSec: z
        .number()
        .int()
        .min(MIN_INTERVAL_SEC)
        .max(3600)
        .optional()
        .describe(`Poll interval in seconds. Default ${DEFAULT_INTERVAL_SEC}, min ${MIN_INTERVAL_SEC}.`),
      events: z
        .array(z.enum(ALL_EVENTS))
        .optional()
        .describe("Which event kinds to report. Default: all of comment, review, status, merge."),
    }),
    approval: "read",
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      let target: (RepoRef & { number: number; kind: Kind }) | null = null;

      if (params.url) {
        target = parseTargetUrl(params.url);
        if (!target) {
          throw new Error(`Could not parse "${params.url}" as a GitHub issue/PR or GitLab issue/MR URL.`);
        }
      } else {
        let ref: RepoRef | null = null;
        if (params.owner && params.repo) {
          const platform = params.platform ?? (params.host === "github.com" ? "github" : "gitlab");
          const host = params.host ?? (platform === "github" ? "github.com" : undefined);
          if (!host) {
            throw new Error("`host` is required alongside `owner`/`repo` when `platform` is gitlab without `url`.");
          }
          ref = { platform, host, owner: params.owner, repo: params.repo };
        } else {
          ref = await inferRepoFromCwd(pi, ctx.cwd);
          if (!ref) {
            throw new Error(
              "Could not infer a repo from the cwd's git remote (not a git repo, or no `origin` remote). " +
                "Provide `url`, or both `owner` and `repo`.",
            );
          }
          if (params.platform) ref = { ...ref, platform: params.platform };
          if (params.host) ref = { ...ref, host: params.host };
        }

        let number = params.number ?? null;
        let kind = params.kind ?? null;
        if (number === null && kind !== "issue") {
          const detected = await detectCurrentPr(pi, ctx.cwd, ref);
          if (detected !== null) {
            number = detected;
            kind = kind ?? "pr";
          }
        }
        if (number === null || kind === null) {
          throw new Error(
            "No `number` given and no open PR/MR found for the current branch. Provide `number` and `kind` " +
              "explicitly, or `url`.",
          );
        }
        target = { ...ref, number, kind };
      }

      const id = subId(target);
      const events = params.events && params.events.length > 0 ? params.events : [...ALL_EVENTS];
      const intervalSec = params.intervalSec ?? DEFAULT_INTERVAL_SEC;

      const existing = subs.get(id);
      const sub: Subscription = {
        id,
        platform: target.platform,
        host: target.host,
        owner: target.owner,
        repo: target.repo,
        number: target.number,
        kind: target.kind,
        intervalSec,
        events,
        createdAt: existing?.createdAt ?? new Date().toISOString(),
      };
      subs.set(id, sub);
      if (!pollStates.has(id)) pollStates.set(id, freshPollState());
      persist(pi, "add", sub);

      // Establish a baseline immediately so the caller sees current state,
      // and so the first background tick doesn't dump the whole history.
      const ps = pollStates.get(id);
      if (!ps) throw new Error("internal: poll state missing after registration");
      let snap: Snapshot | null;
      try {
        snap = sub.platform === "github" ? await fetchGithubSnapshot(deps, sub, signal) : await fetchGitlabSnapshot(deps, sub, signal);
      } catch (err) {
        throw new Error(`Subscribed, but the initial fetch failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      if (!snap) {
        throw new Error(`${labelFor(sub)} was not found (check owner/repo/number/host, and CLI auth).`);
      }
      diffSnapshot(ps, snap, events); // baseline capture, never emits an update
      ps.nextDueAt = Date.now() + intervalSec * 1000;
      ps.lastPolledAt = Date.now();

      return {
        content: [
          {
            type: "text" as const,
            text:
              `${existing ? "Updated" : "Subscribed to"} ${labelFor(sub)} \u2014 "${snap.title}"\n` +
              `state=${snap.state}${snap.merged !== null ? ` merged=${snap.merged}` : ""} ` +
              `comments=${snap.comments.length}${sub.kind === "pr" ? ` reviews=${snap.reviews.length}` : ""}\n` +
              `Polling every ${intervalSec}s for: ${events.join(", ")}. id="${id}"`,
          },
        ],
        details: { id, sub, snapshot: { state: snap.state, merged: snap.merged, title: snap.title, url: snap.url } },
      };
    },
  });

  pi.registerTool({
    name: "watch_unsubscribe",
    label: "Unwatch Issue/PR/MR",
    description: 'Stop watching a subscription created by watch_subscribe. Pass its `id`, or "all" to clear every subscription.',
    parameters: z.object({
      id: z.string().describe('Subscription id from watch_list/watch_subscribe, or "all"'),
    }),
    approval: "read",
    async execute(_toolCallId, params) {
      if (params.id === "all") {
        const removed = [...subs.values()];
        for (const sub of removed) {
          subs.delete(sub.id);
          pollStates.delete(sub.id);
          persist(pi, "remove", { id: sub.id });
        }
        return {
          content: [{ type: "text" as const, text: `Removed ${removed.length} subscription(s).` }],
          details: { removed: removed.map((s) => s.id) },
        };
      }
      const sub = subs.get(params.id);
      if (!sub) {
        return {
          content: [{ type: "text" as const, text: `No active subscription with id "${params.id}".` }],
          details: { removed: false },
        };
      }
      subs.delete(sub.id);
      pollStates.delete(sub.id);
      persist(pi, "remove", { id: sub.id });
      return {
        content: [{ type: "text" as const, text: `Unsubscribed from ${labelFor(sub)}.` }],
        details: { removed: true, id: sub.id },
      };
    },
  });

  pi.registerTool({
    name: "watch_list",
    label: "List Watches",
    description: "List all active GitHub/GitLab issue/PR/MR subscriptions and their last poll status.",
    parameters: z.object({}),
    approval: "read",
    async execute() {
      const list = [...subs.values()].map((sub) => {
        const ps = pollStates.get(sub.id);
        return {
          id: sub.id,
          label: labelFor(sub),
          events: sub.events,
          intervalSec: sub.intervalSec,
          state: ps?.state ?? null,
          merged: ps?.merged ?? null,
          title: ps?.lastTitle ?? null,
          url: ps?.lastUrl ?? null,
          lastPolledAt: ps?.lastPolledAt ? new Date(ps.lastPolledAt).toISOString() : null,
          lastError: ps?.lastError ?? null,
        };
      });
      return {
        content: [
          {
            type: "text" as const,
            text:
              list.length === 0
                ? "No active subscriptions."
                : list
                    .map((s) => `${s.id} \u2014 ${s.title ?? "?"} [${s.state}]${s.lastError ? ` ERROR: ${s.lastError}` : ""}`)
                    .join("\n"),
          },
        ],
        details: { subscriptions: list },
      };
    },
  });
}
