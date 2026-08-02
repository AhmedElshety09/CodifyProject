---
name: tc-converter
description: >
  Step 1 of 2. Converts a raw test case (or loose text) into a structured TC JSON
  and creates its run folder. Use when the user provides a test case ID or pastes a
  test case. The test case ID is the only mandatory field; all other fields are
  derived from the input or predicted, and are included only when the input supports
  them. Each step pairs an action with its expected result. This skill is write-only:
  it never reads runs/ or any existing TC_*.json. On success it creates
  runs/TC_<ID>_<timestamp>/ with empty subfolders (Video, Screenshots, Report,
  Automation, Logs) and a JSON/TC_<ID>.json file, then shows the JSON for approval.
  tc-runner fills the remaining folders.
---

# TC Converter

Convert raw input into a structured JSON test case, create its run folder, and
present the JSON for approval.

## Scope

Write-only. Never list, open, or read `runs/` or any existing `TC_*.json` — the
schema below is the only format reference. The only filesystem actions are
creating `runs/TC_<ID>_<timestamp>/` and writing `JSON/TC_<ID>.json` inside it.
The timestamp guarantees uniqueness, so no collision check or directory listing.

## Fields

| Field | Rule |
|---|---|
| `id` | **Mandatory.** Missing → stop and ask for it. Never invent it. |
| `title` | Short, action-oriented summary. `"UNTITLED"` if none given. |
| `steps` | Required, ordered. Each step = `action` + `expected`. Predict a specific, observable `expected` if the input omits it (tc-runner later refines it against the live page). Never emit `expected_result`. |
| `preconditions` | Only if the user stated some. |
| `test_data` | Only if concrete values are given. |

`id` and `steps` are the only structural keys. Include every other key only when
the input supports it — no empty or placeholder values.

## Schema

```json
{
  "id": "LOGIN_01",
  "title": "Sign in with valid credentials and verify the dashboard",
  "preconditions": ["The user has a valid, active account", "The application URL is reachable"],
  "test_data": { "username": "standard_user", "password": "<from .env / CFG>" },
  "steps": [
    { "step": 1, "action": "Open the application URL", "expected": "The login page is visible with username, password and a submit control" },
    { "step": 2, "action": "Enter a valid username and password", "expected": "Both fields accept the input; no validation error is shown" },
    { "step": 3, "action": "Click the submit control", "expected": "The user is authenticated and redirected to the dashboard" }
  ]
}
```

Minimal case (only required keys):

```json
{
  "id": "SEARCH_01",
  "title": "Search returns matching results",
  "steps": [
    { "step": 1, "action": "Open the application", "expected": "The search box is visible" },
    { "step": 2, "action": "Type a known query and press Enter", "expected": "A results list containing the query term is shown" }
  ]
}
```

## Procedure

1. **Locate the ID.** If none is provided, stop with:
   ```
   Blocked: a test case ID is required to continue.
   The ID is the only mandatory field; everything else can be generated.
   Please provide the test case ID (for example, 27500).
   ```
2. **Build the JSON** from the raw input per the Fields table and Schema above.
3. **Create the folder and write the file** (PowerShell — quote paths, no bash heredocs):
   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
   $run = "runs/TC_<ID>_$stamp"
   New-Item -ItemType Directory -Force -Path "$run/Video","$run/Screenshots","$run/Report","$run/JSON","$run/Automation","$run/Logs" | Out-Null
   ```
   Write the JSON to `$run/JSON/TC_<ID>.json`.
4. **Present and request approval:**
   ```
   Created: runs/TC_<ID>_<stamp>/ (Video, Screenshots, Report, JSON, Automation, Logs)
   Wrote:   JSON/TC_<ID>.json (remaining folders are empty; tc-runner fills them)
   Review the JSON above and reply "approve" to run it with tc-runner.
   ```
