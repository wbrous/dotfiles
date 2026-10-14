#!/usr/bin/env node
// opencode-attest.js — local attestation proxy for OpenCode Zen/Go free tier.
//
// The free-tier gateway only serves requests shaped like the official OpenCode
// client. omp already sends stream:true and the lowercase fingerprint tools
// (bash/glob/grep/read), but its Zen transport stamps
// `x-opencode-session: <uuid>`, which the gateway rejects (it requires
// `ses_<12 hex><14 base62>`), and its `User-Agent: omp/x.y.z` fails the
// `opencode/<semver> >= 1.18.0` check. Config-file headers cannot override
// transport-native headers, so this proxy rewrites them on the way through.
//
//   http://127.0.0.1:8791/zen/v1/* -> https://opencode.ai/zen/v1/*
//   http://127.0.0.1:8791/go/v1/*  -> https://opencode.ai/zen/go/v1/*
//
// Bodies stream through untouched (upstream requires stream:true, which omp
// already sends). Each incoming session value is mapped to one stable
// ses_-format id, mirroring the official client's stable per-session id.

import crypto from "node:crypto";
import http from "node:http";

const PORT = 8791;
const BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
const UA = "opencode/1.19.0";
const SESSION_RE = /^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$/;

function newSessionId() {
  const ts = BigInt(Date.now() & 0xfffffffffff) * 0x1000n + 1n;
  const inv = ~ts & 0xffffffffffffn;
  let hex = "";
  for (let i = 0; i < 6; i++) hex += Number((inv >> BigInt(40 - 8 * i)) & 0xffn).toString(16).padStart(2, "0");
  const bytes = crypto.randomBytes(14);
  let tail = "";
  for (const b of bytes) tail += BASE62[b % 62];
  return `ses_${hex}${tail}`;
}

// Stable mapping so retries within a session keep one id (like the real client).
const sessionMap = new Map();
function attestSession(incoming) {
  if (incoming && SESSION_RE.test(incoming)) return incoming;
  const key = incoming || "none";
  let mapped = sessionMap.get(key);
  if (!mapped) {
    mapped = newSessionId();
    if (sessionMap.size > 1000) sessionMap.delete(sessionMap.keys().next().value);
    sessionMap.set(key, mapped);
  }
  return mapped;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://x");
    let upstream;
    if (url.pathname.startsWith("/zen/v1/")) {
      upstream = "https://opencode.ai/zen/v1/" + url.pathname.slice("/zen/v1/".length) + url.search;
    } else if (url.pathname.startsWith("/go/v1/")) {
      upstream = "https://opencode.ai/zen/go/v1/" + url.pathname.slice("/go/v1/".length) + url.search;
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end('{"error":"unknown prefix; want /zen/v1/* or /go/v1/*"}');
      return;
    }
    const headers = { ...req.headers };
    delete headers.host;
    delete headers.connection;
    delete headers["content-length"];
    delete headers["accept-encoding"];
    headers["user-agent"] = UA;
    headers["x-opencode-client"] = headers["x-opencode-client"] || "desktop";
    headers["x-opencode-session"] = attestSession(headers["x-opencode-session"]);
    const hasBody = req.method !== "GET" && req.method !== "HEAD";
    const upstreamRes = await fetch(upstream, { method: req.method, headers, body: hasBody ? req : undefined, duplex: "half" });
    const outHeaders = {};
    upstreamRes.headers.forEach((v, k) => {
      if (!["content-length", "connection", "transfer-encoding"].includes(k)) outHeaders[k] = v;
    });
    res.writeHead(upstreamRes.status, outHeaders);
    if (upstreamRes.body) for await (const chunk of upstreamRes.body) res.write(chunk);
    res.end();
  } catch (err) {
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: String(err) }));
  }
});

server.listen(PORT, "127.0.0.1", () => console.log(`opencode-attest on 127.0.0.1:${PORT}`));
