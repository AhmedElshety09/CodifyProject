# MeterVerse TC — simple 2-skill automation framework

Paste a raw test case → get back **one folder** with everything:
**Automation (pytest + Playwright) · Video · Screenshots · Report** (+ **Logs** on failure).
A read-only **Suite Dashboard** aggregates every run automatically.

## The idea (spend tokens ONCE)
1. **tc-converter** turns your raw test case into clean JSON + an (empty) folder.
2. **tc-runner** has the **AI execute the test for real** (live via Playwright
   MCP). It captures the **real, robust locators** (`get_by_role` / `get_by_label`
   / `get_by_text` first), refines the expected results, records
   video + screenshots + report, **closes the browser**, and writes a **proven**
   pytest script. **If a step fails**, it writes a diagnostic bundle to `Logs/`.
3. After that, **re-run the script forever with zero tokens.**

```
FIRST TIME (tokens):  AI runs the test LIVE → real locators + video + shots + report
                      → writes Automation/test_TC_<ID>.py → closes the browser
                      → (on failure) writes Logs/ diagnosis
LATER (no tokens):    cd runs && python -m pytest   → same evidence, no AI
```

## The flow (2 steps in chat)
1. **tc-converter** — *"TC with id LOGIN_01: open the app, sign in, verify the
   dashboard."* → agent builds the JSON, makes `runs/TC_LOGIN_01_<time>/`, shows
   the JSON, asks to **approve**.
2. **tc-runner** — you say *"approve"* → the AI runs it live, fills the folder,
   closes the browser, and asks you to run:
   ```powershell
   cd runs && python -m pytest
   ```

### The resulting folder (one per test case)
```
runs/TC_LOGIN_01_<time>/
├── JSON/         TC_LOGIN_01.json          ← the approved contract (expecteds refined)
├── Automation/   test_TC_LOGIN_01.py       ← proven pytest + Playwright
│                 locators.json             ← the Observer-phase locator map
├── Screenshots/  step_01.png … step_NN.png ← one per step
├── Video/        run.webm                  ← the execution recording
├── Report/       report.html + result.json ← the report
└── Logs/         run.log + step_NN.error.json + summary.md   ← ONLY if a step fails
```

## Setup (once)
```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium

# Configure EVERYTHING in .env (copy the template, then edit):
Copy-Item .env.example .env
# set MV_BASE_URL and, if needed, MV_USER / MV_PASS
```

## Run the automation tests (token-free, any time)
```powershell
# The command tc-runner asks you to run — runs every generated test:
cd runs && python -m pytest

# Other useful forms (from the project root):
python -m pytest example_test.py            # the template smoke test
python -m pytest -k "LOGIN_01"              # by name (substring)
python -m pytest "runs/TC_LOGIN_01_<ts>/Automation/test_TC_LOGIN_01.py"
```
After any run, open **`dashboard/dashboard.html`** (auto-refreshed) for the suite view.

## Files
```
conftest.py        ← THE ENGINE: CFG (from .env) + reporter + video + timeouts + logs + report
example_test.py    ← the GENERAL, ideal template the runner mimics
.env / .env.example← ALL configuration (nothing hard-coded in code)
requirements.txt · pytest.ini · .gitignore
README.md · ARCHITECTURE.md
.agents/skills/
├── tc-converter/SKILL.md
└── tc-runner/SKILL.md
dashboard/
└── build_dashboard.py   ← READ-ONLY; writes dashboard.html from runs/ (auto after each pytest)
```

## Everything is configured in `.env` (nothing hard-coded)

| .env key | Meaning |
|---|---|
| `MV_BASE_URL` | App under test |
| `MV_USER` / `MV_PASS` | Login for preconditions |
| `MV_BROWSER` | `chromium` \| `firefox` \| `webkit` |
| `MV_HEADLESS` | `true` = background |
| `MV_VIEWPORT_W/H` | Browser size |
| `MV_T_ACTION/NAV/EXPECT` | Timeouts (ms) — nothing hangs forever |
| `MV_VIDEO` | Record video (mandatory) |
| `MV_FAIL_SHOT_MAX_H` | Cap the failure full-page screenshot height |
| `MV_LOG_MAX_CONSOLE/NETWORK/TB_LINES` | Caps for the failure log bundle |

Generated tests receive config as a **fixture**: `def test_TC_<ID>(page, CFG, reporter):`.

## Failure diagnostics (only on failure)
When a step fails, the engine writes `Logs/`:
- **`run.log`** — full timeline of the run (every step + timings).
- **`step_NN.error.json`** — machine record: category (`TIMEOUT` / `LOCATOR_NOT_FOUND`
  / `ASSERTION` / `NETWORK` / `STEP_LOGIC` / `UNKNOWN`), error, URL, page title,
  **console errors**, **failed network requests**, traceback tail.
- **`summary.md`** — human-readable; during a live tc-runner session the AI
  refines this with a specific root-cause + fix.

## The Suite Dashboard (read-only, auto)
`dashboard/build_dashboard.py` scans `runs/` and writes a self-contained
`dashboard/dashboard.html` — KPIs, pass-rate, flaky count, **failure categories**,
a failures-first list, a searchable/sortable table, and per-test history dots. It
**auto-refreshes** after each `pytest` run (A2 hook in `conftest.py`), or run it
manually: `python dashboard/build_dashboard.py`.

## Why it just works
- **AI executes for real first** → the script uses locators it **verified live**.
- **Config from `.env`** → change the target app in one place, no code edits.
- **Video** native via Playwright → `Video/run.webm`.
- **No hanging** → CFG timeouts bound every action/nav/assert.
- **pytest anywhere** → `pytest.ini` makes `cd runs && python -m pytest` work.
