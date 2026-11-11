# Security Audits

Static triage of downloaded source, compiled mod jars, and PHP2Shell (CVE-2026-109618/109619) exposure assessment — without running untrusted code or exploit payloads.

## Auditing downloaded source for malware

**Symptom:** "Is this a virus / safe / backdoored?" about a downloaded source tree, compiled mod jar, or decompiled Java.

**Static triage (never execute):**

1. Inventory: `find . -type f | wc -l`, list tree; identify from metadata (fabric.mod.json, package.json, pom): id, author, homepage, entrypoints, nested jars.
2. Binaries: `find . -type f \( -name "*.jar" -o -name "*.dll" -o -name "*.so" -o -name "*.exe" -o -name "*.class" \)`. Source-only with none = good sign; nested jars listed in metadata but absent can't be checked.
3. Network surface: `grep -rlE "java\.net\.(http|URL|Socket|URI)|HttpURLConnection|HttpClient|new URL\(|new Socket"`, then all hardcoded hosts: `grep -rhoE "https?://..." | sed host | sort | uniq -c`. Every host must be explainable (auth providers, Discord, CDN, project GitHub); unknown hosts/IPs = red flag.
4. Execution/dynamic loading: grep `ProcessBuilder|Runtime.getRuntime().exec|defineClass|URLClassLoader|System.load|Class.forName`. Ignore `availableProcessors()`; `Class.forName` targets are usually optional-mod lookups; `MethodHandles` strings in javac output are lambda boilerplate.
5. Credential theft: in files with network use, grep `token|Account|Credentials|session|accessToken`; confirm webhook/Discord code never touches auth data and tokens go only to Microsoft/Xbox/Mojang endpoints. Note plaintext-JSON token storage as a risk.
6. Report: separate "no malware indicators" from non-malware risks (cheat clients → bans; plaintext tokens), state what was NOT reviewed, advise: run only jars built from source or official releases; check hash/VirusTotal.

**Compiled jars / hidden-op (server mods, anticheats):** NEVER vouch from one small jar — a few-KB jar is usually a version-adapter shim; the real code is in sibling/nested jars (past case: clean shim, 14MB meta-jar had the backdoor). Fabric meta-mods nest jars (`META-INF/jars/*.jar`); recursively extract ALL levels (python zipfile walk, dedupe sha256, one dir per jar) into /tmp/flat, then count classes per jar to separate author code from third-party libs. Tools: `unzip`, `javap -p -c -constants`, `strings -a`, `grep -rlaE` over .class files. Hidden-op hunt: class/method names `*Op*`, `registerHidden`, `dispatchCommand`/`performCommand` + `getConsoleSender`; hardcoded player-name checks (`ldc String <name>` + `equalsIgnoreCase(Sender.getName())`, `static final String ALLOWED_NAME`) — grep the string across the tree; if in ONE class with no help/lang/yml/permission reference, it's hidden. Command preprocessors matching raw `/<modname> op` bypass permission nodes. Get dispatched strings via `javap -p -v` on `makeConcatWithConstants` bootstrap args. Expected legit network in Grim-based anticheats: bStats, api.grim.ac, paste.grim.ac, user-configured Discord webhook, crafthead.net. Final report: exact file/class, what it checks, what it runs, why hidden, what wasn't reviewed, remediation.

_Migrated from: audit-downloaded-source-for-malware_

## PHP2Shell exposure assessment (CVE-2026-109618 / CVE-2026-109619)

**Scope:** two critical PHP RCEs disclosed 2026-10-21 — 109618: OOM handling leaves corrupt interpreter state; 109619: stale global/request state reuse → UAF/memory disclosure. This is exposure assessment and remediation, NOT payload creation. A public version string is exposure evidence, not proof of exploitability.

**Version/patch assessment:** fixed releases PHP 8.2.35, 8.3.36, 8.4.27, 8.5.12. PHP 7.4–8.1: no new upstream release, minimal source backports only. 7.3 and older unsupported. Check the actual web SAPI/runtime and vendor changelog — never infer the runtime from a stale error, cached page, header, or unrelated CLI binary. For PHP 7.2 say the branch is unsupported and needs migration or a vendor package; don't claim no backport exists without checking the vendor.

**Safe evidence:** `php -v` + FPM/mod_php equivalent, package version + vendor advisory, runtime config/SAPI, public version disclosure (labeled fingerprint-only), post-patch logs + worker restarts. Never test public sites with exploit payloads.

**Remediation:** update to a fixed release or trusted vendor backport; restart ALL PHP workers; verify the running web runtime. `session.upload_progress.enabled=0` covers only relevant session paths, not every 109618 path; config changes and WAF rules are not substitutes for patching. On public sites set `display_errors=Off`, log privately, verify error pages no longer leak paths/versions.

**Research sources (start here, before third-party PoCs):** https://calif.io/php2shell/, GHSA-w8hw-w9fx-j79w, GHSA-6wmf-4rv5-p3rp, https://www.php.net/archive/2026.php#2026-10-21-5. Third-party https://github.com/ikow/php2shell-poc is unverified — static inspection found `privileged: true`, `seccomp:unconfined`, all-interface ports, deliberate LFI/system-execution endpoints, and scanner verdicts overstating passive fingerprints; clone for static inspection only, never run its lab/scripts. Tenable: circulating exploit code unverified, possibly malware. Sophos: exploitation config-dependent and nontrivial; scanning ≠ compromise.

**Safe local config lab:** purpose-built Docker Compose only — pin image digest, bind `127.0.0.1`, read-only webroot/php.ini mounts, `read_only: true`, tmpfs, `no-new-privileges`, limits, dropped caps (Apache needs narrowly re-added SETUID/SETGID; never privileged). Diagnostic endpoint reports `PHP_VERSION`/`PHP_SAPI`/`memory_limit`/`session.upload_progress.enabled`/`display_errors` as JSON (config evidence, not exploit test). `curl http://127.0.0.1:<port>/`, then `docker compose down`. Keep the service up while using published ports; `internal: true` networks block port forwarding. Distinguish: (1) exposed version string, (2) upstream-affected version, (3) patched runtime, (4) demonstrated exploitability. Never leave test containers running.

_Migrated from: php-cve-2026-109618-109619-php2shell-assessment_
