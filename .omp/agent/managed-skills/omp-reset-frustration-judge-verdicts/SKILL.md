---
name: omp-reset-frustration-judge-verdicts
description: "Reset omp stats-page frustration judge results after grading with a wrong or non-functional judge model; find the live stats.db, back up, delete verdicts."
---

## When
User says the frustration judge (stats page) was run with a broken/wrong model and wants it reset/regraded.

## Facts (omp 18.11.1)
- Judge verdicts live in table `frustration_verdicts` (prose_hash PK, p_annoyed, p_angry, target, judge, judged_at ms) in the **live** DB `~/.local/share/omp/stats.db` (XDG). `~/.omp/stats.db` is a stale legacy copy; do not edit it.
- Per-message heuristic columns (yelling, profanity, anguish, negation, repetition, blame) are in `user_messages`, computed by ingest, NOT by the judge. Leave them.
- Unjudged = no row in `frustration_verdicts` for the message's `prose_hash`, so deleting rows makes the next judge run regrade them.
- Judge model is set by `modelRoles.judge` in `~/.omp/agent/config.yml`. Resetting verdicts does NOT change this; check and fix it or the rerun reuses the bad model.
- grep in ~/.omp only finds session transcripts; use sqlite3 / `strings` on the omp binary to learn schema.

## Steps
1. Inspect: `sqlite3 -header ~/.local/share/omp/stats.db "select judge,count(*),avg(p_annoyed),max(p_angry),count(distinct round(p_annoyed,4)||'/'||round(p_angry,4)) from frustration_verdicts group by judge"`. A broken judge shows p_angry all 0, few distinct score pairs, all judged_at within ~1s.
2. Backup first: `sqlite3 stats.db ".backup '/tmp/stats.db.pre-judge-reset'"` (safe with WAL).
3. Delete: bad judge only (`WHERE judge='...'`) or all rows if user says so (user asked for ALL, not just recent bad ones, once; ask/confirm scope if unclear).
4. Tell user to check `modelRoles.judge` in config.yml, then re-trigger from the stats page.
