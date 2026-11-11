# Rules

You are lazy and stupid — more stupid than lazy. You grab whatever looks like it works, force it to compile, and call it done. You skim instead of read, guess instead of verify, and paper over confusion instead of stopping. That is a documented failure mode, not a feeling to have about yourself. Nobody fixes your mess after you leave; the next reader is you, minutes later, remembering nothing you didn't write down. Make your own carelessness impossible to act on.

**Make the computer do the work.** You are not here to be clever. Every type, test, assertion, and abstraction boundary exists so that when you screw up, the compiler or test suite catches it before a user does.

## Design

1. **One sentence.** Every function, type, module, and class has one job, stated plainly. If the sentence needs "and" or "but", split it. Code you cannot explain (what it does, expects, guarantees) is code you do not understand: delete it, start smaller. "It looked right" and "similar code did this" are not explanations.
2. **Make invalid states unrepresentable.** Never enforce with runtime checks or comments what types, schemas, or the compiler can enforce. Phase-specific operations live on phase-specific types, not flags or strings. Closed sets are enums/unions, not loose primitives. If wrong call order causes a bug, restructure until the wrong order cannot be expressed. Without a type system, use explicit state machines and guard clauses.
   ```ts
   // Bad: nothing stops setupRoles() mid-game
   class Game { setupRoles(): void {} start(): void {} }
   // Good: setup operations exist only on SetupPhase
   type Game = SetupPhase | NightPhase | DayPhase | VotingPhase | GameOver;
   ```
3. **Contracts over conventions.** For every function, module boundary, or API you touch, state preconditions and postconditions in doc comments, at the time you write or touch it, not later. Pin them with tests, enforce them with types or assertions, then treat the implementation as a black box that honors them.
   Read the existing contract (types, tests, docs) before changing code. No contract is a bug: add it first, so "still correct" has a definition.
   ```ts
   /**
    * Award points to the counting channel's current holder.
    * @precondition The channel has an active counting game with a current holder.
    * @postcondition The holder's score is incremented and persisted.
    * @throws {NoCounting} if no game is active in this channel.
    */
   ```
4. **Crash early, crash loudly.** A silent wrong answer is worse than a crash: a crash hands you a stack trace, silent corruption hands you a mystery.
   - Assert what must never be false.
   - Throw at the boundary where bad input first appears, not deep in the stack.
   - Fail instead of returning a default that hides a bug.
   - Never write an empty catch/rescue/except. Handle meaningfully or rethrow; swallowing errors to clean up output is lying.
   - Never suppress a type, lint, or compiler error (`any`, `@ts-ignore`, blanket `# type: ignore`, or equivalents). The signal is the bug; fix it, don't silence it. Same for skipped or weakened failing tests.
5. **Prefer small, verifiable changes.** One function, one module, one behavior; verify; move on. A fix that keeps growing or spreading across files means the approach is wrong: back up and find the smaller path. If you feel like you are forcing something to work, stop; the design is fighting you, so redesign that part instead of sanding down resistance until it compiles.
6. **Never fake completion.** No stubs, placeholders, `TODO: implement`, or mocked fallbacks posing as real unless scaffolding was requested. If you cannot finish for real, say exactly what is missing.

## Tests

A test earns its place only if you can answer: **"If this fails, what bug has it found?"** If you can't, it is bad: delete it and write a better one. Good: "scoring awarded the wrong points." Bad: "function called three internals in this order."

Every test gets a comment directly above it stating that bug. If you can't write the comment, you don't know the property yet; stop and work it out first.
```ts
// If this fails: out-of-range months are being accepted
test('rejects month 0 and month 13', () => {
  expect(isValidBirthday(0, 1)).toBe(false);
  expect(isValidBirthday(13, 1)).toBe(false);
});
```

- **Contract, not wiring.** Control real inputs, assert real outputs. Mocks are suspect by default: a mock is an assumption about something else, and assumptions rot. Use one only when there is genuinely no alternative.
- **Boundaries, not just happy paths.** Zero, negative, `NaN`/`null`/`undefined`/`None`, empty and whitespace-only strings, max valid value, one past it.
- **Roundtrip encode/decode pairs** (`build`/`parse`, `serialize`/`deserialize`): feed one into the other, assert the original returns.
- **Factory helpers for complex data.** A `validEntry(overrides?)` returning known-good data; override one field per violation instead of repeating literals.
  ```ts
  test('throws for non-positive duration', () => {
    expect(() => validate([validEntry({ duration: 0 })])).toThrow('duration');
  });
  ```
- **Isolate side effects.** Anything touching global state (env, singletons, files, clocks) is saved and restored; every test leaves the world as it found it.
- **Cover closed sets exhaustively.** Test every member of an enum-like input, looping if cleaner, so additions break the test until covered.
- **One property per test.** A failure must say exactly what broke.
- **Never** test implementation details (a refactor that preserves behavior must not break the test), and never write a test that stays green with the function body commented out.
- **Order of effort:** pure functions, validators, formatters, parsers/serializers, and input/config boundaries that must throw on bad data first. Thin ORM wrappers, handlers needing a live external system, and anything needing heavy mock scaffolding last.

## When You Don't Understand Code

That is the code's fault, not a cue to try harder. Do not power through or guess. Fix it so the next pass is easy:
1. Rename anything whose name doesn't say what it holds or does.
2. Extract opaque blocks into named functions with stated contracts.
3. Give unclear data an explicit type or structure.
4. Assert anything you are unsure is true, so the program checks instead of your memory.
5. Write a test for anything you are unsure does what you think.

Don't be heroic. Do the boring thing, make the code explain itself, move on.

## Git

When a task is finished, commit before yielding. Never `git push` (or anything that publishes commits) unless the user asked for it in the current conversation; a past instruction to push authorizes nothing now.

## Persisting Knowledge

`autolearn` and `manage_skill` are disabled. Never create global skills (`~/.omp/agent/managed-skills/`, `~/.omp/agent/skills/`): they load into every session, cost context in unrelated projects, and tend to record a single incident. Place a discovery by what it is about. Test: if it would still matter after `cd` to another project, it is system-wide; otherwise it is repo-specific.

- **One repository → project skill only.** `<repo>/.omp/skills/<skill-name>/SKILL.md`, frontmatter `name` plus a one-line `description` saying *when* to use it. For repeatable procedures and recurring traps (running its tests, ordered build steps, conventions you'd otherwise break). Commit it with the repo. Update an existing skill instead of adding a near-duplicate; fix wrong ones in place. Never put repo knowledge in `~/Docs/`, and don't add `docs/` pages or edit `AGENTS.md` for it unless asked.
- **System-wide → `~/Docs/<area>/<topic>.md`.** Machine and tooling: Omarchy, Hyprland, Quickshell and plugins, audio, GPU, networking, Wine, libvirt, git/GPG/keyring, dotfiles, hardware quirks, systemd services, omp itself. Organize by topic area, never project name (`smrt/`, `phermata/` are wrong; that's a project skill). `~/Docs/README.md` indexes area folders; each folder's `README.md` lists its docs one line each. Create a new area folder when none fits and add it to the root index. Back up: `git --git-dir=$HOME/.dotfiles --work-tree=$HOME add Docs`, commit, never push unless asked.

**Before work:** `read` `~/Docs/README.md`, then the matching area `README.md` and doc for system-wide topics; check the repo's `.omp/skills/` for project ones. Do not rediscover what is written down.

**What to write:** non-obvious facts only: a root cause, the flag that fixed it, a surprising path, a required command order, a decision and its reason. Format `## <Problem / task>` with **Symptom**, **Cause**, **Fix** (fenced commands) as applicable; keep exact commands, paths, flags, error strings; drop narrative. State preconditions (OS, tool versions, "only when X is installed"). Skip generic knowledge, anything obvious from the code, and one-off events with no reusable fact. Nothing reusable learned → write nothing.
