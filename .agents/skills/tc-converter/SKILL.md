---
name: tc-converter
description: >
  Step 1 of 2. Converts a raw test case into a structured TC JSON and creates its run
  folder, keyed by the Azure DevOps work item ID. Use when the user provides a test
  case ID or pastes a test case. The ID is the only mandatory field and must not
  already have a runs/<ID>/ folder — if it does, the converter stops rather than
  overwrite it. All other fields are derived from the input or predicted, included
  only when the input supports them. Each step pairs an action with its expected
  result. When an action in the input is vague (for example "click a button"), the
  converter resolves it to the concrete action and lists that step in a top-level
  guesses array so tc-runner verifies it first. Predicted expected results are NOT
  guesses. This skill only ever checks for the exact runs/<ID>/ folder name; it
  never opens or reads any existing test case JSON. If a business-critical detail is
  missing (something the live page could never supply), the converter stops, writes
  businessGaps/<ID>.json (overwriting any prior one), and does not create the run
  folder. Otherwise it self-checks the JSON against the schema, then creates
  runs/<ID>/ with empty subfolders (Video, Screenshots, Report, Automation, Logs)
  and a JSON/<ID>.json file written as UTF-8 without a BOM, then shows the JSON
  for approval. tc-runner fills the remaining folders.
---
 
# TC Converter
 
Convert raw input into a structured JSON test case, self-check it, create its run
folder, and present the JSON for approval. The folder is keyed to the ID alone —
one ID, one run, forever, matching how Azure DevOps already identifies the work item.
 
## Scope (write little, read nothing — one narrow exception)
 
Write-only. Never open or read any existing test case JSON, and never list or browse
`runs/` in general. The **one** exception: before building anything, check whether
the exact folder `runs/<ID>/` already exists (a plain `Test-Path`, not a
directory listing, not a read of its contents). That single check is what makes the
ID-keyed folder safe.
 
The only filesystem writes are `runs/<ID>/JSON/<ID>.json`, or, on a business
gap, `businessGaps/<ID>.json` (freely overwritten if one already exists — it's a
note, not a result).
 
All files are written UTF-8 **without a BOM** via .NET's `WriteAllText` — never
`Set-Content -Encoding utf8`, which adds a BOM that breaks JSON parsers downstream.
 
## Collision gate (hard block)
 
```powershell
if (Test-Path "runs/<ID>") {
    # STOP. Do not create, do not overwrite, do not touch its contents.
}
```
 
If it already exists, stop immediately and tell the user:
```
Blocked: runs/<ID>/ already exists.
Each ID gets exactly one run. Remove or rename that folder yourself if you intend
to rebuild it, then re-run this skill.
```
Do not proceed to the business-gap check or JSON build when blocked.
 
## Fields
 
| Field | Rule |
|---|---|
| `id` | Mandatory, `^[A-Za-z0-9_-]+$`. Missing → stop and ask. Never invent it. |
| `title` | Short, action-oriented. `"UNTITLED"` if none given. |
| `steps` | Required, non-empty, 1-based sequential (`step: 1, 2, 3...`). Each = `action` + `expected`. Predict a specific, observable `expected` if omitted (tc-runner refines it against the live page). Never emit `expected_result`. |
| `preconditions` | Only if the user stated some. |
| `test_data` | Only if concrete values are given. |
| `guesses` | Optional array of `steps[N].action` paths — **only** for actions you had to interpret from vague input (e.g. "click a button"). `N` = that step's own 1-based `step` number. Never list `expected` here — predicting `expected` is normal, not a guess. Omit entirely if nothing was vague; never an empty array. |
 
`id` and `steps` are the only structural keys. Include every other key only when
the input supports it — no empty or placeholder values.
 
## Business-gap gate
 
Before building the JSON, apply this test to every uncertainty:
 
> **Could the live website tell me this?**
> Yes → surface detail only (vague action, label, wording). Resolve it, continue,
> record it in `guesses`.
> No → business intent or data is missing entirely (e.g. "apply the discount" with
> no rule given). This is a **business gap** — stop.
 
On a business gap: do not create the run folder. Write `businessGaps/<ID>.json`
(create the folder if it doesn't exist; overwrite freely if it already exists):
 
```json
{
  "id": "LOGIN_01",
  "reason": "The expected outcome depends on the account's permission level, which the test case never specifies.",
  "missing": "Which permission/role the test account should have",
  "where": "step 3"
}
```
 
Then tell the user:
```
Business gap: this test case cannot be built accurately as written.
Wrote: businessGaps/<ID>.json
Missing: <one line on what is needed>
Provide the missing business detail and I will build the test case.
```
 
Never fabricate business data to get past this — a test that passes on invented
data proves nothing.
 
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
 
Minimal case (no vague actions, so `guesses` is omitted):
 
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
 
Case with a resolved vague action (index matches the step's own 1-based number):
 
```json
{
  "id": "CART_01",
  "title": "Add a product and open the cart",
  "steps": [
    { "step": 1, "action": "Open the application", "expected": "The products page is visible" },
    { "step": 2, "action": "Add the Sauce Labs Backpack to the cart", "expected": "The cart badge shows 1 item" },
    { "step": 3, "action": "Click the cart icon", "expected": "The cart page lists the added product" }
  ],
  "guesses": ["steps[2].action"]
}
```
 
## Self-check before writing
 
Confirm against the Fields table above — mentally, no shelling out, no reading
files: `id` matches its pattern; every step has non-empty `action` and `expected`;
no `expected_result` anywhere; `guesses` (if present) only contains `action` paths
whose index matches that step's own number. Fix anything that fails before writing.
 
## Procedure
 
1. **Collision check.** `Test-Path "runs/<ID>"`. If it exists, stop with the
   Blocked message above — do not check for business gaps or build anything.
2. **Business-gap check.** If the gate above finds a gap, write/overwrite
   `businessGaps/<ID>.json` and stop — do not create the run folder.
3. **Build the JSON** per the Fields table and Schema above.
4. **Self-check** it; fix any failures.
5. **Write it** (PowerShell — quote paths, no bash heredocs, no BOM):
   ```powershell
   $run = "runs/<ID>"
   New-Item -ItemType Directory -Force -Path "$run/Video","$run/Screenshots","$run/Report","$run/JSON","$run/Automation","$run/Logs" | Out-Null
 
   $json = $testCase | ConvertTo-Json -Depth 10
   $path = Join-Path (Resolve-Path $run) "JSON/<ID>.json"
   [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
   ```
   `-Depth 10` avoids silent truncation of nested `steps`/`test_data`. `UTF8Encoding($false)` = no BOM.
6. **Present and request approval:**
   ```
   Created: runs/<ID>/ (Video, Screenshots, Report, JSON, Automation, Logs)
   Wrote:   JSON/<ID>.json (remaining folders are empty; tc-runner fills them)
   Review the JSON above and reply "approve" to run it with tc-runner.
   ```
