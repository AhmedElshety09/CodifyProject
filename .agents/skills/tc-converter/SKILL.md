---
name: tc-converter
description: >
  Step 1 of 2. Converts a raw test case into a structured TC JSON and creates its run
  folder. Use when the user provides a test case ID or pastes a test case. The test
  case ID is the only mandatory field; all other fields are derived from the input or
  predicted, and are included only when the input supports them. Each step pairs an
  action with its expected result. When an action in the input is vague (for example
  "click a button"), the converter resolves it to the concrete action and lists that
  field's path in a top-level guesses array so tc-runner verifies it first. Predicted
  expected results are NOT guesses. This skill is write-only and reads nothing: it
  never lists runs/ and never opens any existing TC_*.json. If a business-critical
  detail is missing (something the live page could never supply), the converter stops,
  writes businessGaps/<ID>.json, and does not create the run folder. Otherwise it
  self-checks the JSON against the schema, then creates runs/TC_<ID>_<timestamp>/ with
  empty subfolders (Video, Screenshots, Report, Automation, Logs) and a
  JSON/TC_<ID>.json file written as UTF-8 without a BOM, then shows the JSON for
  approval. tc-runner fills the remaining folders.
---

# TC Converter

Convert raw input into a structured JSON test case, self-check it, create its run
folder, and present the JSON for approval. The test case ID is the only hard
requirement.

There is no external validator. All files are written as UTF-8 **without a BOM**
using .NET's `WriteAllText`, so nothing downstream (tc-runner, pytest) can ever
choke on an invisible byte.

## Scope (read nothing)

Write-only. Do not inspect the workspace before building the test case:

- Never list, open, or read `runs/` or any existing `TC_*.json`.
- Do not check folder structure, count existing runs, or explore the project.
- The schema in this file is the only format reference.

The only filesystem actions are creating `runs/TC_<ID>_<timestamp>/` and writing
`JSON/TC_<ID>.json` inside it — or, when a business gap is found, writing a single
`businessGaps/<ID>.json` instead. The timestamp guarantees uniqueness, so no
collision check or directory listing.

## Fields

| Field | Rule |
|---|---|
| `id` | Mandatory. Missing → stop and ask for it. Never invent it. Must match `^[A-Za-z0-9_-]+$`. |
| `title` | Short, action-oriented summary. `"UNTITLED"` if none given. |
| `steps` | Required, non-empty, ordered (1-based, sequential). Each step = `action` + `expected`. If an action is vague (e.g. "click a button", "add any product"), **rewrite it to the concrete action** and record its path in `guesses`. Predict a specific, observable `expected` if the input omits it (tc-runner later refines it against the live page). Never emit `expected_result`. |
| `preconditions` | Only if the user stated some. |
| `test_data` | Only if concrete values are given. |
| `guesses` | Optional. Paths of **actions you had to interpret** (or other input values you inferred). NOT for predicted `expected` results. Omit the key entirely when nothing was interpreted. |

`id` and `steps` are the only structural keys. Include every other key only when
the input supports it — no empty or placeholder values.

## Guess-marking

Predicting each step's `expected` is the converter's **normal job** — it is **not**
a guess, and tc-runner refines every `expected` against the live page regardless.
**Never list `expected` fields in `guesses`.**

A guess is different: it is when the **input's action is vague or underspecified**
and you commit to a specific interpretation. When this happens you must do **two**
things:

1. **Resolve it** — rewrite the vague action into the concrete action you believe is
   meant, using the surrounding context. Do not leave "click a button" as-is.
2. **Flag it** — add that step's `action` path to `guesses` so tc-runner verifies
   your interpretation first.

Rule of thumb — `guesses` answers **"which actions did I have to *interpret*?"**, not
"which expecteds did I predict?" (that would be all of them, which is useless).

- Use **0-based** array indices: `steps[0].action` is the first step, `steps[1]` the
  second, and so on. Also valid: `test_data.<key>`.
- If no action was vague and nothing was inferred, **omit the `guesses` key** — never
  write an empty array.

This is distinct from a business gap: a guess means "the action was vague but I can
reasonably interpret it and the live page will confirm it"; a business gap means "I
cannot build this at all without missing business data" (see the Business-gap gate).

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

Minimal case (only required keys — no vague actions, so `guesses` is omitted):

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

Case with a resolved vague action (`guesses` marks only the interpreted action):

```json
{
  "id": "CART_01",
  "title": "Add a product and open the cart",
  "steps": [
    { "step": 1, "action": "Open the application", "expected": "The products page is visible" },
    { "step": 2, "action": "Add the Sauce Labs Backpack to the cart", "expected": "The cart badge shows 1 item" },
    { "step": 3, "action": "Click the cart icon", "expected": "The cart page lists the added product" }
  ],
  "guesses": ["steps[1].action"]
}
```

## Self-check (inline, no external tool)

Before writing, confirm the JSON satisfies all of the following. This is a mental
checklist — do not shell out, do not run any script, do not read any file:

- `id` is present and matches `^[A-Za-z0-9_-]+$`.
- `steps` is a non-empty array; each `step` is 1-based and sequential (1, 2, 3, ...).
- Every step has a non-empty `action` and a non-empty `expected`.
- No step contains `expected_result`.
- `preconditions`, `test_data`, `guesses` appear only when warranted and are the
  right type (array of strings / object / array of strings).
- Every path in `guesses` points at a real `action` (never an `expected`).

If any check fails, fix the JSON before writing. Do not create the run folder until
all checks pass.

## Business-gap gate

Before building the JSON, decide whether the input is complete enough to produce a
meaningful test. Apply one test to every uncertainty:

> **Could the live website tell me this?**
> Yes → it is only a surface detail (a vague action, a label, wording, or selector).
> Do NOT stop; resolve it to the concrete action, continue, and record its path in
> `guesses`.
> No → the intent or required business data is missing. This is a business gap.

A business gap is when the test's outcome depends on a rule, value, permission,
threshold, or data that the input never provides and no amount of looking at the
page could reveal (for example, "apply the discount" with no discount rule given).

When a business gap is found, **stop and do not create the run folder.** Write a
single file `businessGaps/<ID>.json` (UTF-8, no BOM — see the write method below),
then tell the user:

```
Business gap: this test case cannot be built accurately as written.
Wrote: businessGaps/<ID>.json
Missing: <one line on what is needed>
Provide the missing business detail and I will build the test case.
```

`businessGaps/<ID>.json` format (kept minimal):

```json
{
  "id": "LOGIN_01",
  "reason": "The expected outcome depends on the account's permission level, which the test case never specifies.",
  "missing": "Which permission/role the test account should have",
  "where": "step 3"
}
```

Do not fabricate business data to get past this. A test that passes on invented
data proves nothing.

## Procedure

1. **Check for business gaps** using the Business-gap gate above. If a gap exists,
   write `businessGaps/<ID>.json`, do NOT create the run folder, and stop.

2. **Build the JSON** from the raw input per the Fields table and Schema above.
   Resolve any vague action to a concrete one and record its `action` path in
   `guesses` (omit the key if no action was vague). Do not list predicted `expected`
   results in `guesses`.

3. **Self-check** the JSON against the Self-check list above. Fix anything that
   fails before writing.

4. **Create the folder and write the file** (PowerShell — quote paths, no bash
   heredocs). Always write with `[System.IO.File]::WriteAllText`, which produces
   UTF-8 **without a BOM** — never use `Set-Content -Encoding utf8` (it adds a BOM
   that breaks JSON parsers downstream).
   ```powershell
   $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
   $run = "runs/TC_<ID>_$stamp"
   New-Item -ItemType Directory -Force -Path "$run/Video","$run/Screenshots","$run/Report","$run/JSON","$run/Automation","$run/Logs" | Out-Null

   $path = Join-Path (Resolve-Path $run) "JSON/TC_<ID>.json"
   [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
   ```
   `New-Object System.Text.UTF8Encoding($false)` = UTF-8, BOM disabled. This is the
   single most important line: no BOM is ever written, so no parser ever fails on one.

5. **Present and request approval:**
   ```
   Created: runs/TC_<ID>_<stamp>/ (Video, Screenshots, Report, JSON, Automation, Logs)
   Wrote:   JSON/TC_<ID>.json (remaining folders are empty; tc-runner fills them)
   Review the JSON above and reply "approve" to run it with tc-runner.
   ```

## Rules

- Read nothing. Never list or open `runs/` or any existing `TC_*.json`. Do not
  inspect workspace structure. There is no external validator to read or run.
- The ID is the only stop. Output is JSON only.
- **Always write files with `[System.IO.File]::WriteAllText` using
  `UTF8Encoding($false)` (no BOM). Never use `Set-Content -Encoding utf8`.**
- If a business-critical detail is missing (the live page could never supply it),
  stop, write `businessGaps/<ID>.json`, and do not create the run folder. Never
  fabricate business data to get past a gap.
- Every step carries both an `action` and an `expected`. Never emit `expected_result`.
- Resolve vague actions to concrete ones and record only those `action` paths in
  `guesses`. Never list predicted `expected` results as guesses. Omit `guesses` when
  no action was interpreted (never write an empty array).
- Include a key only when the input supports it; no placeholder values.
- Shell is PowerShell; quote paths; no bash heredocs.
- The only filesystem writes are the new `runs/TC_<ID>_<timestamp>/` folder with its
  `JSON/TC_<ID>.json` — or a single `businessGaps/<ID>.json` when a gap is found.
