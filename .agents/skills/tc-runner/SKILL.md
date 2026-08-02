---
name: tc-runner
description: STEP 2 of 2. Runs when the user says "approve" / "run" after
  tc-converter. The AI EXECUTES the test case LIVE via Playwright MCP first
  (Observer -> Author): it OBSERVES the live DOM to capture robust semantic
  locators, saves them to Automation/locators.json, refines each step's expected
  result, captures a screenshot per step + video + report, CLOSES the browser,
  then AUTHORS a standalone pytest + Playwright (Python) script into
  Automation/test_TC_<ID>.py. On any failure it enriches Logs/summary.md with a
  root-cause diagnosis. Finally it asks the user to run `cd runs && python -m pytest`.
  All settings come from .env via conftest.py CFG.
---

## TC Runner — Live AI Run (Observer ➔ Author) → Re-runnable ▶️

### The philosophy (why this order matters)
You **spend tokens once**: the AI drives the browser and performs the test for
real. That real run produces the evidence AND captures the **exact, robust
locators that work**, so the generated script is **proven and working**, not
guessed. After this, the script runs by itself with **no tokens**.

```
FIRST TIME (tokens):  Observe live DOM → capture real locators (locators.json)
                      → refine expecteds → run steps (video + shots + report)
                      → CLOSE the browser → Author Automation/test_TC_<ID>.py
LATER (no tokens):    cd runs && python -m pytest → same evidence, no AI
```

**Result — one folder holds the deliverables:**
```
runs/TC_<ID>_<timestamp>/
├── JSON/TC_<ID>.json            ← input (expecteds refined by this skill)
├── Screenshots/step_NN.png      ← captured during the live AI run
├── Video/run.webm               ← the live AI run recording
├── Report/report.html + result.json
├── Automation/
│   ├── test_TC_<ID>.py          ← proven pytest + Playwright, re-runnable token-free
│   └── locators.json            ← the Observer-phase locator map
└── Logs/                        ← ONLY on failure: run.log + step_NN.error.json + summary.md
```

### ⚙️ One config source — `.env`
Everything (base_url, username/password, browser, headless, viewport, timeouts,
video, fail-shot cap, log caps) lives in **`.env`**, loaded by `conftest.py` into
**CFG** and exposed as the **`CFG` fixture**. Never hard-code — read from CFG.

---

## ⛔ Hard rules
1. **Execute for REAL first, then author.** Drive the browser live via Playwright
   MCP (`browser_navigate`, `browser_click`, `browser_type`, `browser_press_key`,
   `browser_snapshot`, `browser_take_screenshot`). Write the script from what
   actually worked — never from imagination.
2. **CLOSE the browser when the live run is done** (`browser_close`) — mandatory,
   also on BLOCKED/failure.
3. **Shell is Windows PowerShell.** No bash heredocs (`<<`); quote spaced paths.
4. **The generated script MUST be collectable:** function starts with `test_`,
   signature is **`(page, CFG, reporter)`**, one `reporter.step(...)` per JSON
   step. No `test_` function = "no tests ran". Never emit that.

---

## The Observer ➔ Author workflow (per page visited)

### Phase A — OBSERVER: live observation & element capture
Before writing code, analyze the **live** DOM / accessibility tree and capture the
most robust locator for each needed element.

**Locator priority (highest first):**
1. **User-facing / semantic:** `get_by_role`, `get_by_text`, `get_by_label`,
   `get_by_placeholder`.
2. **Test attributes:** `get_by_test_id` (`data-testid`).
3. **Structural:** `get_by_id` / stable, shallow CSS.
- **Strictly avoid** brittle locators (long XPath, deeply nested CSS).
- **Handle live edge cases:** dropdowns, modals, dynamic loading, iframes, shadow DOM.
- **Save the locator map** to `Automation/locators.json`.

### Phase B — AUTHOR: refine expecteds + write the script
- **Refine each step's expected** (write it **back into `JSON/TC_<ID>.json`**):
  - **Scenario A — user provided one:** follow it exactly.
  - **Scenario B — none provided:** infer from the action + captured locator's state.
- **Author `Automation/test_TC_<ID>.py`** in the EXACT shape of `example_test.py`
  (signature `(page, CFG, reporter)`, one `reporter.step(...)` per step, semantic
  locators, Playwright auto-waiting + explicit `expect(...)` with `CFG["t_expect"]`).

---

## Procedure

### 🟢 Phase 0 — Prepare (once)
```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```
Locate the newest `runs/TC_<ID>_<timestamp>/`; read `JSON/TC_<ID>.json`.
Re-validate: `id` present, ≥1 step, every step has `expected`. If not → STOP.
Set `$env:TC_RUN_DIR = "runs/TC_<ID>_<timestamp>"` so all evidence lands here.

### 🔵 Phase 1 — Execute LIVE via MCP (Observer)
Open the browser. Satisfy preconditions (log in with `CFG["username"]`/
`CFG["password"]` if needed, else `goto CFG["base_url"]`; if the start state can't
be reached → mark **BLOCKED**, close the browser, stop). For each JSON step:
perform the action via MCP, screenshot to `Screenshots/step_NN.png`, capture the
robust locator, and refine the expected. Stop on first failure.
**When finished, CLOSE the browser (`browser_close`);** the video finalizes to
`Video/run.webm`.

### 🟣 Phase 2 — Author + persist
Write `Automation/locators.json`; write refined expecteds back into
`JSON/TC_<ID>.json`; write `Automation/test_TC_<ID>.py` from the captured locators.

### 🩺 Phase 2.5 — On FAILURE: enrich the diagnostic summary
Logs are written **only when a step fails**. The engine (`conftest.py`)
automatically produces a **mechanical baseline** in `Logs/`:
- `run.log` — full timeline of the run,
- `step_NN.error.json` — structured record (category, error, URL, page title,
  **console errors**, **failed network requests**, traceback tail),
- `summary.md` — an auto-generated baseline summary.

**Your job when a failure exists:** read `Logs/step_NN.error.json` and **overwrite
`Logs/summary.md`** with a sharper, human diagnosis. Use the machine `category`
(`TIMEOUT` / `LOCATOR_NOT_FOUND` / `ASSERTION` / `NETWORK` / `STEP_LOGIC` /
`UNKNOWN`) plus the console/network evidence to explain, specifically:
1. **What failed** (the step + the observable symptom).
2. **Why** (root cause — e.g. "the Submit button stayed disabled because step 2's
   email field showed a validation error — see console error X").
3. **Is it the test or the app?** (a flaky/locator issue in the test vs. a real
   product bug vs. environment/network).
4. **Concrete fix** (e.g. "add a wait for the spinner", "use
   `get_by_role('button', name='Submit')`", "raise `MV_T_ACTION`", or "file a bug —
   the API returned 500").
Keep it concise and actionable. Do **not** edit `run.log` or the `.error.json`
(those are the raw record); only refine `summary.md`.

### 🟢 Phase 3 — Ask the user to run the automation
Tell the user the framework is ready and ask them to run the token-free suite:
```powershell
cd runs && python -m pytest
```

### Phase 4 — Summarize
Post the verdict + step counts and links to `Report/report.html`,
`Video/run.webm`, `Automation/test_TC_<ID>.py`, and `Automation/locators.json`.
**If it failed**, also link `Logs/summary.md` and state the category + one-line
root cause. Then give the `cd runs && python -m pytest` command.

---

## Verdict
| Situation | Verdict |
|---|---|
| All steps passed | **PASS** |
| A step's expected not met / timed out | **FAIL** (stops there; Logs/ written) |
| Precondition unreachable | **BLOCKED** (no steps run) |

## Rules
- **Observe first (capture real, semantic locators), then author.** Proven, not guessed.
- Prefer role/label/text locators; avoid brittle XPath/nested CSS.
- Save `Automation/locators.json`; refine expecteds and write them back to the JSON.
- **Close the browser when the live run ends** (`browser_close`) — mandatory.
- **On failure, enrich `Logs/summary.md`** with a root-cause diagnosis (don't touch
  `run.log` or `step_NN.error.json`).
- Config comes from `.env` via CFG; tests take `(page, CFG, reporter)`.
- End by asking the user to run: `cd runs && python -m pytest`.
- PowerShell only; never bash heredocs.
