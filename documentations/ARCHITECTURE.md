# MeterVerse Test-Case Automation — Full Architecture & Implementation Guide

> **Purpose.** The single, authoritative reference for the whole project: every
> file, what it does, how the pieces talk, the two AI skills, the workflow, the
> JSON contract, the runtime engine, the failure logs, and the read-only
> dashboard. Written to be complete and accurate so we can build on it.
>
> **Status:** validated in a sandbox — `.env` config loads into CFG (nothing
> hard-coded), the `CFG` fixture resolves, `cd runs && python -m pytest` finds
> the root engine, the failure-log bundle writes only on failure (6/6 categories
> classify correctly), and the dashboard JSON parses in a real JS engine.

---

## 1. What this project is (in one paragraph)

A user pastes a **raw test case** into an AI agent in VS Code. Two **Agent
Skills** turn it into a **runnable, self-documenting test**:

1. **`tc-converter`** formats the raw input into a standard **JSON** and creates
   one folder for that test case (empty subfolders + the JSON).
2. **`tc-runner`** has the **AI execute the test live** (via Playwright MCP) using
   an **Observer ➔ Author** workflow: it observes the live page to capture robust
   locators, saves them, refines each step's expected result, captures the
   **video + screenshots + report**, **closes the browser**, then writes a
   standalone **pytest + Playwright (Python)** script. **On failure** it writes a
   diagnostic bundle to `Logs/`.

**The economic idea:** you spend AI tokens **once** (the live run). After that,
anyone re-runs the generated pytest scripts **with zero tokens** via
`cd runs && python -m pytest`.

**The deliverable:** for every test case, one folder with **Automation, Video,
Screenshots, Report** (+ **Logs** on failure). A read-only **dashboard**
aggregates all runs.

---

## 2. The two-phase philosophy (the core design principle)

```
┌─────────────────────────── FIRST TIME (spends tokens) ───────────────────────────┐
│  tc-converter:  raw text ─► TC_<ID>.json  (+ empty run folder)                     │
│  user approves                                                                     │
│  tc-runner (Observer ➔ Author), live via Playwright MCP:                           │
│     • OBSERVE the live DOM → capture robust, semantic locators → locators.json     │
│     • REFINE each step's expected result against the real page                     │
│     • run each step → screenshot per step + session video + report                 │
│     • on FAILURE → write Logs/ (run.log + step_NN.error.json + summary.md)         │
│     • CLOSE the browser (MCP browser_close)                                        │
│     ─► AUTHOR Automation/test_TC_<ID>.py from the PROVEN locators                  │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── LATER (zero tokens) ─────────────────────────────────┐
│  cd runs && python -m pytest                                                       │
│  conftest.py engine auto-produces: Video/run.webm, Screenshots/, Report/,          │
│  (+ Logs/ on failure) per test, and refreshes dashboard/dashboard.html             │
└────────────────────────────────────────────────────────────────────────────────────┘
```

**Why "execute live first, then codify":** acting for real first means the AI only
writes locators it has **already verified work** (semantic first: `get_by_role`,
`get_by_label`, `get_by_text`). The final automation is **working**, not guessed.

---

## 3. Project file tree (every file)

```
meterverse-tc/
├── conftest.py                         ← THE ENGINE (CFG-from-.env + reporter + logs + fixtures)
├── example_test.py                     ← the GENERAL ideal template the runner mimics
├── .env                                ← ALL configuration (git-ignored; local secrets)
├── .env.example                        ← safe committed template for .env
├── pytest.ini                          ← pytest config (pythonpath + importlib mode)
├── requirements.txt                    ← one-time dependency install
├── .gitignore                          ← ignores .env, runs/, dashboard.html, caches
├── README.md                           ← quick-start for humans
├── ARCHITECTURE.md                     ← this document (full reference)
│
├── .agents/skills/                     ← the two AI Agent Skills (SKILL.md standard)
│   ├── tc-converter/SKILL.md           ← STEP 1: raw text ─► JSON + empty folders (the GATE)
│   └── tc-runner/SKILL.md              ← STEP 2: live Observer➔Author ─► fills the folder
│
├── dashboard/
│   └── build_dashboard.py              ← READ-ONLY; writes dashboard.html from runs/ (auto A2)
│
└── runs/                               ← created at RUNTIME (git-ignored); one folder per test case
    └── TC_<ID>_<YYYYMMDD_HHMMSS>/
        ├── JSON/         TC_<ID>.json           (tc-converter; expecteds refined by tc-runner)
        ├── Automation/   test_TC_<ID>.py + locators.json  (tc-runner)
        ├── Screenshots/  step_01.png … step_NN.png
        ├── Video/        run.webm
        ├── Report/       report.html + result.json
        └── Logs/         run.log + step_NN.error.json + summary.md   (ONLY on failure)
```

Run folders are always `TC_<ID>_<timestamp>` — never `TC_manual_`.

---

## 4. File-by-file reference

### 4.1 `conftest.py` — THE ENGINE
Auto-discovered by pytest; every test (even deep in `runs/.../Automation/`) gets
its fixtures. Loads `.env` first, then:

**CFG (from `.env`):** `base_url`, `username`/`password`, `browser`, `headless`,
`viewport`, `t_action`/`t_nav`/`t_expect`, `wait_until`, `video`/`video_name`,
`fail_shot_max_h`, and log caps (`log_max_console`/`network`/`tb_lines`). Nothing
hard-coded. Also exposed as the **`CFG` fixture**.

**Folders:** `SUBS` includes `Logs`. `run_dir(tc_id)` resolves the run folder
(`TC_RUN_DIR` if set, else cached `runs/TC_<tc_id>_<ts>/`). `save_locator_map()`
writes `Automation/locators.json`.

**Failure diagnostics:** `_classify_failure()` buckets errors into `TIMEOUT`,
`LOCATOR_NOT_FOUND`, `ASSERTION`, `NETWORK`, `STEP_LOGIC`, `UNKNOWN`.
`CATEGORY_HINT` gives a plain-English likely cause. `_page_context()` grabs URL +
title at failure.

**Reporter:**
- `_shot()` — normal screenshot on pass; capped full-page on fail
  (`fail_shot_max_h`).
- `step()` — wraps one step; records pass/fail; builds a `timeline`; **on failure
  calls `_log_failure()`** then re-raises (stop-on-first-failure).
- `_log_failure()` — **only on failure** writes `Logs/run.log`,
  `Logs/step_NN.error.json` (category, error, URL, title, **console errors**,
  **failed requests**, traceback tail), and a baseline `Logs/summary.md`.
- `finalize()` — writes `Report/result.json` + `report.html`.

**Fixtures:** `CFG`; `browser_type_launch_args` (headless); `browser_context_args`
(viewport + native video); `page` (timeouts **+ console/network collectors**
stashed on the page for failure logging); `reporter`. `pytest_sessionfinish`
renames the video **and runs the A2 dashboard refresh**. `pytest_configure`
registers markers.

### 4.2 `example_test.py` — the general template
Site-agnostic; drives `CFG["base_url"]`, asserts `body` visible, and carries
commented examples (semantic locators, Scenario A/B expecteds, a login block).
Signature `(page, CFG, reporter)`. tc-runner mimics this shape exactly.

### 4.3 `pytest.ini`
`pythonpath = .` + `--import-mode=importlib`. Makes deep tests reach the root
fixtures and makes **`cd runs && python -m pytest`** resolve `rootdir` to the
project root (validated).

### 4.4 `.env` / `.env.example`
Every setting (see §4.1). `.env` is git-ignored; `.env.example` is the template.

### 4.5 `requirements.txt`
`pytest`, `pytest-playwright`, `playwright`, `python-dotenv`. Install with
`python -m pip install -r requirements.txt` then `python -m playwright install chromium`.

### 4.6 `README.md`, 4.7 `.gitignore`
Human quick-start; and ignores `.env`, `runs/`, `dashboard/dashboard.html`, caches.

### 4.8 `tc-converter/SKILL.md`
Creates the folder with **empty** `Video/Screenshots/Report/Automation/Logs` +
`JSON/TC_<ID>.json`. Gate on the ID.

### 4.9 `tc-runner/SKILL.md`
Observer➔Author; locator priority; `locators.json`; refine expecteds back into the
JSON; **close the browser**; **Phase 2.5 — on failure, enrich `Logs/summary.md`**;
handoff `cd runs && python -m pytest`.

### 4.10 `dashboard/build_dashboard.py`
READ-ONLY. Scans `runs/*/Report/result.json`, reads any `Logs/*.error.json` for
the failure category, and writes a self-contained `dashboard.html` (KPIs,
pass-rate ring, flaky count, **failure categories**, failures-first list,
searchable/sortable table, per-test history dots, links incl. 🪵 logs). Called
by the A2 hook after each run, or manually.

---

## 5. The data contract — the JSON

`tc-converter` writes it; `tc-runner` reads it and refines `expected` back into it.
Mandatory field: `id` (the only gate). Optional: `title` (→ `UNTITLED`),
`preconditions` (only if stated), `test_data`. `steps[]` have
`step/action/expected/expected_result`. `credentials_key` is **never** emitted
(credentials come from `.env`).

```json
{
  "id": "LOGIN_01",
  "title": "Sign in and verify the dashboard",
  "test_data": {},
  "steps": [
    { "step": 1, "action": "Open the application", "expected": "The login page is visible", "expected_result": "pass" }
  ]
}
```

---

## 6. Skill 1 — tc-converter (the Gate 🚦)
Gate on the ID (never invent) → build JSON → create `runs/TC_<ID>_<ts>/` with the
five empty subfolders + `JSON/TC_<ID>.json` → show JSON → ask "approve". JSON
only; PowerShell; folder under `runs/`.

---

## 7. Skill 2 — tc-runner (Live Observer ➔ Author ▶️)

- **Observer:** capture robust locators live (semantic → test-id → structural;
  avoid XPath/deep CSS; handle modals/iframes/shadow DOM) → save `locators.json`.
- **Author:** refine each expected (Scenario A follow user's / B infer) → write
  back to the JSON → write `Automation/test_TC_<ID>.py` in the `example_test.py`
  shape (`(page, CFG, reporter)`, one `reporter.step()` per step, `expect(...)`).
- **Close the browser** (`browser_close`) when the live run ends.
- **Phase 2.5 (on failure):** read `Logs/step_NN.error.json` and **overwrite
  `Logs/summary.md`** with a specific root cause (test vs app vs env) + a concrete
  fix. Do not edit `run.log` or the `.error.json`.
- **Handoff:** ask the user to run `cd runs && python -m pytest`.

**Verdict:** PASS / FAIL (stops; Logs written) / BLOCKED (no steps run).

---

## 8. How everything talks (relationships)

```
   RAW TEXT ─► tc-converter ─► runs/TC_<ID>_<ts>/JSON/TC_<ID>.json
                                     │ (approve)
                                     ▼
   tc-runner ──live MCP──► browser ──► screenshots/video/report
        │  (Observer captures locators; on fail writes Logs/)
        │  browser_close
        ▼
   Automation/test_TC_<ID>.py   def test_TC_<ID>(page, CFG, reporter)
        │  cd runs && python -m pytest  (token-free)
        ▼
   conftest.py ENGINE ─► video · screenshots · report (+ Logs on fail)
        │  pytest_sessionfinish
        ▼
   dashboard/build_dashboard.py ─► dashboard.html  (read-only, A2 auto)
```

**Who writes/reads:** JSON (converter→runner), test_TC/locators (runner→pytest),
screenshots/video/report/logs (engine→humans+dashboard), CFG (.env→everything),
dashboard.html (builder→humans).

**Critical couplings:** `.env` (all config), `TC_RUN_DIR` (folder handoff),
`pytest.ini pythonpath` (deep imports + `cd runs`), the A2 hook (auto dashboard).

---

## 9. End-to-end walkthrough
Converter builds JSON + empty folders → you approve → runner runs live, captures
locators + evidence, (on failure writes Logs), closes the browser, authors the
pytest script, and asks you to run `cd runs && python -m pytest`. Re-runs are
token-free and refresh the dashboard automatically.

---

## 10. Setup & commands (PowerShell)
```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env        # set MV_BASE_URL (+ MV_USER/MV_PASS if needed)

python -m pytest example_test.py   # prove the framework
cd runs && python -m pytest        # token-free suite (what tc-runner asks)
python dashboard/build_dashboard.py  # manual dashboard refresh (also auto)
```

---

## 11. Problems this design solves
- **Video** → native `record_video_dir` → `Video/run.webm` (version-independent).
- **Hanging** → CFG timeouts bound every action/nav/assert.
- **"No tests"/pytest** → strict `test_(page, CFG, reporter)` shape + `pytest.ini`.
- **Blind failures** → `Logs/` bundle (category + console + network + summary).
- **No overview** → read-only dashboard aggregating all runs.

---

## 12. Design decisions
Single-file engine; all config in `.env`; standalone pytest tests; observe-then-author
with locator priority; refine expecteds back to JSON; close the browser; logs
**only on failure** with size caps; BLOCKED ≠ FAIL; dashboard is read-only + separate;
`.env`/`runs/`/`dashboard.html` git-ignored.

---

## 13. Recommended next things (roadmap)
- **Dashboard failure-category trends over time** (weekly).
- **Locator drift detection** — compare live locators to saved `locators.json`;
  flag `LOCATOR_DRIFT` (self-healing signal).
- **Auto-retry once on TIMEOUT/NETWORK** (opt-in) to separate flaky from broken.
- **Trace on failure** (`playwright show-trace`) — opt-in, heavier.
- **`data-testid` wishlist** — log elements lacking stable locators for devs.
- **CI / Azure DevOps** — publish report+video as artifacts; post PASS/FAIL to a
  Test Plan.

---

## 14. Glossary
**Skill** = SKILL.md instructions. **Playwright MCP** = server the AI uses to drive
a live browser (closed with `browser_close`). **Observer➔Author** = capture real
locators, then author the script. **Run folder** = `runs/TC_<ID>_<ts>/`. **Engine**
= `conftest.py`. **CFG** = config dict from `.env`, also a fixture. **Logs** =
failure-only diagnostics. **Dashboard** = read-only aggregate view.

---

*End of document. Keep it updated whenever files, the JSON contract, the skills,
the logs, or the dashboard change — it is the source of truth for the project.*
