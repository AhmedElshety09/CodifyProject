---
name: tc-runner
description: >
  Step 2 of 2. Proves a converter-approved test case live against the real
  application, then freezes it into a permanent pytest + Playwright script. Use when
  the user asks to run, execute, or prove a test case that tc-converter has already
  approved at runs/<ID>/JSON/<ID>.json. Requires a Playwright browser MCP connector;
  if none is available, stop and say so rather than attempt it. Never creates or
  renames folders — it only fills the empty subfolders tc-converter already created
  (Video, Screenshots, Report, Automation, and, only on failure, Logs). If
  runs/<ID>/Automation/test_<ID>.py already exists, it skips straight to running
  pytest — no live browser, no tokens spent. Otherwise it drives a real browser step
  by step (Observer), grounding every locator and every assertion in Playwright MCP's
  live accessibility snapshot rather than trusting the contract, with one bounded
  retry per step on transient failure. Any step whose observed outcome contradicts
  what was predicted — not just worded differently, but a different result — is a
  failure, not a refinement: the runner stops, writes a Logs/ diagnostic bundle, and
  does not author a script. Only when every step passes does it write the refined JSON
  contract, the locator map, the generated test_<ID>.py, and report.html (Author).
  Assumes conftest.py (the project engine: browser/page fixtures, video recording,
  timeouts, reporting) already exists and never creates or modifies it.
---

# TC Runner

"Don't imagine a test — perform it, then write it down."

Where tc-converter describes intent, tc-runner proves that intent against the real
application and freezes it into a reusable script. You pay the model once, live, to
convert intent into proof; every run after that is free — pure Python and Playwright,
no AI, no tokens.

| Phase | Tokens | When |
|---|---|---|
| Observer + Author | Yes | Once, to prove the test live and write the script |
| `python -m pytest` | None | Every run after — pure Python + Playwright |

It never creates or renames folders. tc-converter already made `runs/<ID>/`; the
runner only fills the empty subfolders left behind.

## Prerequisites (stop honestly if unmet)

- **Contract exists:** `runs/<ID>/JSON/<ID>.json`. Missing → stop, tell the user to
  run tc-converter first. This skill proves a contract, never builds one.
- **Playwright MCP connector available.** Missing → stop and say so. Never fake or
  skip the live phase.
- **`conftest.py` is assumed to exist** — the project engine that provides the
  browser/page fixtures, video recording, timeouts, and reporting. Never create,
  modify, or touch it.
- Never create or rename folders — only fill the subfolders already inside
  `runs/<ID>/`.

## Environment is already set up (do not check or install)

The Python environment is installed **once, by the user, outside this skill** —
`pip install -r requirements.txt` and `playwright install` have already been run.
Treat the environment as ready on every invocation:

- Do **NOT** read, open, or inspect `requirements.txt`.
- Do **NOT** run `pip install`, `pip check`, `playwright install`, or any dependency
  or version check — not for the first test case, not for any test case.
- Do **NOT** verify that packages exist before running. Assume Playwright, pytest, and
  all dependencies are present.
- If a dependency were genuinely missing, `pytest` would fail with a clear import
  error — that is the user's cue to reinstall, not a reason for this skill to probe
  the environment.

Go straight to the Idempotency check. The only setup that ever runs is the user's
one-time install; this skill never repeats it.

## Idempotency (check first, always)

If `runs/<ID>/Automation/test_<ID>.py` already exists:
```powershell
cd runs; python -m pytest -k "<ID>"
```
Report the result and stop — do not enter Observer. Re-observing an already-proven
test wastes tokens for nothing.

*(To force a fresh run, delete or rename `runs/<ID>/` and re-run tc-converter — there
is no separate re-observe path in this skill.)*

If the script doesn't exist yet, proceed to Phase 1.

## Inputs

- **Contract:** `JSON/<ID>.json`, read as UTF-8 (tolerate a stray BOM).
- **guesses:** `steps[N].action` paths, 1-based — `N` matches that step's own
  `"step"` number. These are the interpretations to verify first.
- **test_data:** any concrete values the contract carries (e.g. a username/password
  for a login step) are used directly as ordinary step inputs. There is no separate
  credential mechanism.

## The core mechanism — full page snapshot as ground truth

Steps may be AI-generated, so locators are never known in advance — the contract
cannot be trusted to say where things are. Instead, on every page load or significant
navigation, capture Playwright MCP's native accessibility snapshot (roles, names, and
structure of everything visible) and use it as ground truth for three jobs:

- **Resolve locators** for actions and assertions.
- **Disambiguate vague assertions** — e.g. "verify the word 'Product' exists" is only
  resolvable against the live page, which reveals whether it's an `h1`, a `span`, a
  button label, etc.
- **Refine the contract** — when a step is underspecified, the snapshot supplies the
  concrete detail so the Author writes precise automation.

The snapshot covers: headings (with levels), visible text (with parent context),
interactive elements (role, label/aria, visible text), media (alt/title), tables
(headers, row/column labels), lists, status/badge text, and layout anchors (section
titles, tabs, breadcrumbs).

**Persistence:** the full snapshot lives only in memory during Observer — it's already
what MCP returns, so capturing it costs nothing extra, and there is no reason to
persist a giant `snapshot.json` per page. Only the *resolved* per-step locator map is
persisted, to `Automation/locators.json`, written incrementally as each step resolves
— so it is always accurate and never lost to a crash mid-run. On failure, the current
page's snapshot is dumped into `Logs/` as debugging evidence — that is where the full
picture earns its keep.

## Locator resolution (strict priority — stop at first unique, stable match)

1. `get_by_role(role, name=...)` — accessible role + visible name
2. `get_by_label(...)` — form labels
3. `get_by_text(...)` — exact/substring visible text
4. `get_by_test_id(...)` — `data-testid`
5. `id` / CSS — last-resort fallback

Observed locators are solid; guessed ones are fragile — which is exactly why
resolution happens live, never statically.

## Phase 1 — Observer (live, spends tokens)

For each step, in order:

1. **Snapshot** the current page — ground truth for what is actually there.
2. **Resolve the target locator** for this step's action from the snapshot, by the
   priority above.
3. **Act.** Perform the action via Playwright MCP using that locator. On a transient
   failure (timeout, locator not found), retry once after a short backoff before
   treating it as real.
4. **Snapshot again** to capture the result of the action. Playwright MCP typically
   returns this automatically as part of the action response, so this second snapshot
   usually costs nothing extra.
5. **Resolve the assertion** from that post-action snapshot: disambiguate vague checks
   (find the actual element and its tag/role) and confirm the concrete locator/value
   being asserted on.
6. **Screenshot** the result to `Screenshots/step_NN.png` (NN = this step's own
   1-based number, zero-padded).
7. **Compare `expected` against reality:**
   - Wording or specificity differs only → refine `expected` to what was actually
     observed.
   - The observed outcome contradicts the *meaning* of the prediction (e.g. predicted
     success, got an error) → this is a **failure**, not a refinement. Stop and go to
     Failure handling. Never rewrite a semantic mismatch into a "confirmed" expected —
     that would freeze a bug into a passing script.
8. **Resolve guesses.** If this step's action is in `guesses`: the live page confirmed
   the interpretation in steps 1–5 above → keep it; it contradicted it → overwrite the
   action with the true one. Either way, write the exact concrete action and the exact
   observed locator to `locators.json` now, and drop the path from `guesses`. The
   Author must only ever see the specific, verified action — never the original vague
   phrasing. After a clean run, `guesses` is empty.

Record `Video/run.webm` throughout — pass or fail — and close the browser cleanly when
done.

## Failure handling

If any step fails (after its one retry):

- Stop. Do not proceed to Author. Do not write a passing script.
- Finalize `Video/run.webm` and close the browser before reporting — no orphan
  processes.
- Write to `Logs/`:
  - `run.log` — ordered trace of the run.
  - `step_NN.error.json` — expected vs. actual, the locator tried, a screenshot
    reference.
  - `summary.md` — one-paragraph plain-English diagnosis.
  - `snapshot_step_NN.json` — the failing page's full snapshot, as debugging evidence.
- Write a minimal `Report/report.html` — status failed, which step failed, links to
  screenshots, video, and `Logs/`. Every run stays visible; a failure is never a
  blank folder.
- Report the failure to the user with the summary. A failure usually means a real
  problem in the test or the app — diagnose first, never author a script that didn't
  pass.

## Phase 2 — Author (only if every step passed)

1. Write the refined contract back to `JSON/<ID>.json` — refined `expected`s,
   `guesses` now empty — UTF-8, no BOM (`[System.IO.File]::WriteAllText` +
   `UTF8Encoding($false)`; never `Set-Content -Encoding utf8`).
2. Finalize `Automation/locators.json` — the complete observed step-to-locator map.
3. Generate `Automation/test_<ID>.py` — pytest + Playwright using only the observed
   locators, one test function, steps in order, a short comment per step mirroring the
   concrete action, asserting each refined `expected`, and driving navigation and
   inputs from the contract's own steps and `test_data`. It relies on the existing
   `conftest.py` fixtures for the browser/page and recording — it does not create or
   configure them.
4. Write the full `Report/report.html` — per-step pass, timings, links to screenshots
   and video. (No `result.json` — `report.html` is the single report artifact: full on
   pass, minimal on failure.)
5. Clear any stale `Logs/` from an earlier failed attempt on this ID — a passing
   script should never sit next to old failure diagnostics.

## Finished folder

```
runs/<ID>/
├── JSON/        <ID>.json              # approved contract — expecteds refined, guesses resolved
├── Automation/  test_<ID>.py           # proven pytest + Playwright
│               locators.json           # observed step-to-locator map, written live per step
├── Screenshots/ step_01.png … step_NN.png   # only executed steps
├── Video/       run.webm               # finalized on pass OR fail
├── Report/      report.html            # full on pass; minimal on failure
└── Logs/        run.log + step_NN.error.json + summary.md + snapshot_step_NN.json   # only on failure
```

## Consistency with tc-converter

- Same ID-keyed folder — fills `runs/<ID>/`, never spawns a second run or renames it.
- Same 1-based `guesses` indexing, read exactly as written.
- Same BOM-free write discipline everywhere.
- Business gaps never reach this skill — on a gap the converter never creates the run
  folder, so there's nothing here to execute.
