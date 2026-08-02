---
name: tc-converter
description: STEP 1 of 2. Turns a raw test case (or loose text, or any test-case
  structure) into standard TC JSON and creates its folder. Use when the user says
  "TC with id ..." or pastes a test case. The ONLY mandatory field is the test
  case ID; everything else the agent derives, defaults, or predicts. On success
  it creates runs/TC_<ID>_<timestamp>/ with the EMPTY subfolders (Video,
  Screenshots, Report, Automation, Logs) plus a JSON/ folder containing
  TC_<ID>.json, then shows the JSON for approval. tc-runner fills the rest.
---

## TC Converter — the Gate 🚦

Turn raw input into a clean JSON test case, create its folder, show it, ask to
approve. The **only hard requirement is the test case ID**.

### One folder per test case
The converter creates ONE folder: `runs/TC_<ID>_<timestamp>/`. It leaves
`Video/`, `Screenshots/`, `Report/`, `Automation/`, and `Logs/` **empty**, and
writes only `JSON/TC_<ID>.json`. tc-runner fills the empty folders later (video,
screenshots, report, the pytest automation, and — only if a step fails — logs).

### Field rules
| Field | Rule |
|---|---|
| **id** | **MANDATORY.** The only STOP. If missing → ask and wait. Never invent it. |
| **title** | If none given → `"UNTITLED"`. |
| **steps** | Use provided steps, or derive them from the raw text. |
| **expected** (per step) | If omitted → **predict** a specific, observable result. (tc-runner refines these against the real page.) |
| **preconditions** | Include **only if** the user stated some; else omit the key. |
| **test_data** | From concrete values in the input; else `{}`. |

*(No `credentials_key` — the runner handles login from `.env` via CFG.)*

### JSON format
```json
{
  "id": "LOGIN_01",
  "title": "Sign in and verify the dashboard",
  "test_data": {},
  "steps": [
    { "step": 1, "action": "Open the application", "expected": "The login page is visible", "expected_result": "pass" },
    { "step": 2, "action": "Enter valid username and password and submit", "expected": "The dashboard is shown", "expected_result": "pass" }
  ]
}
```
If the user stated preconditions, add a `"preconditions": [ "..." ]` array right
after `title`.

### Procedure
1. **Gate:** find an **ID**. If none → STOP:
   ```
   🚦 GATE: BLOCKED — I need a Test Case ID to continue.
   The ID is the only mandatory field; everything else I can generate.
   ➡️ Please provide the test case ID (e.g., 27500).
   ```
2. **Build the JSON** per the format above (title→UNTITLED if missing; derive
   steps; predict missing expected; preconditions only if stated).
3. **Create the folder + write JSON** (PowerShell):
   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
   $run = "runs/TC_<ID>_$stamp"
   New-Item -ItemType Directory -Force -Path "$run/Video","$run/Screenshots","$run/Report","$run/JSON","$run/Automation","$run/Logs" | Out-Null
   ```
   Write the JSON to `$run/JSON/TC_<ID>.json`. **Remember the exact folder name.**
4. **Show + approve:**
   ```
   🚦 GATE: PASSED ✅
   📁 Created: runs/TC_<ID>_<stamp>/ (Video, Screenshots, Report, JSON, Automation, Logs)
   📄 Wrote:  JSON/TC_<ID>.json  (other folders are empty; tc-runner fills them)
   Please review the JSON above and reply "approve" to run it with tc-runner.
   ```

### Rules
- ID is the only STOP. Output is **JSON only** (no `.md` output).
- Shell is **PowerShell**; quote paths; never bash heredocs.
- Folder lives under **runs/** so tc-runner can find it and pytest can fill it.
