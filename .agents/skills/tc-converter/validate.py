#!/usr/bin/env python
"""
validate.py - tc-converter hard-fail gate.

Deterministic, token-free check that a candidate TC JSON matches the tc-converter
schema BEFORE anything is written to disk. It uses only the Python standard
library and never calls a model.

Exit codes:
    0  = valid   -> the converter may create the folder and write the file
    1  = invalid -> every problem is printed to stderr; the converter must NOT write
    2  = usage / unreadable input / malformed JSON

Usage (PowerShell):
    # From stdin (recommended - nothing hits disk until this passes):
    $json | python .agents/skills/tc-converter/validate.py --stdin

    # From a file:
    python .agents/skills/tc-converter/validate.py path/to/TC_<ID>.json
"""

import argparse
import json
import re
import sys

# region config
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
REQUIRED_STEP_KEYS = ("step", "action", "expected")
# endregion


# region validation
def validate(data):
    """Return a list of human-readable error strings. Empty list means valid."""
    errors = []

    if not isinstance(data, dict):
        return ["Top-level JSON must be an object."]

    # id: mandatory and path-safe
    tc_id = data.get("id")
    if not tc_id or not isinstance(tc_id, str):
        errors.append("Missing mandatory 'id' (non-empty string).")
    elif not ID_PATTERN.match(tc_id):
        errors.append(f"'id' must match ^[A-Za-z0-9_-]+$ (got: {tc_id!r}).")

    # title: optional, but must be a string if present
    if "title" in data and not isinstance(data["title"], str):
        errors.append("'title' must be a string when present.")

    # steps: required, non-empty, ordered, each an action+expected pair
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("'steps' must be a non-empty array.")
    else:
        for i, step in enumerate(steps):
            where = f"steps[{i}]"
            if not isinstance(step, dict):
                errors.append(f"{where} must be an object.")
                continue
            # sequential 1-based numbering
            num = step.get("step")
            if not isinstance(num, int):
                errors.append(f"{where}.step must be an integer.")
            elif num != i + 1:
                errors.append(f"{where}.step must be {i + 1} (got {num}); steps are 1-based and sequential.")
            # action + expected must both be present, non-empty strings
            for key in ("action", "expected"):
                val = step.get(key)
                if not val or not isinstance(val, str):
                    errors.append(f"{where}.{key} must be a non-empty string.")
            # expected_result is forbidden at conversion time
            if "expected_result" in step:
                errors.append(f"{where}.expected_result must NOT be present; the runner writes real results.")
            # no unknown keys inside a step
            for key in step:
                if key not in REQUIRED_STEP_KEYS:
                    errors.append(f"{where} has unexpected key '{key}' (allowed: step, action, expected).")

    # preconditions: optional, array of strings if present
    if "preconditions" in data:
        pc = data["preconditions"]
        if not isinstance(pc, list) or not all(isinstance(x, str) for x in pc):
            errors.append("'preconditions' must be an array of strings when present.")

    # test_data: optional, object if present
    if "test_data" in data and not isinstance(data["test_data"], dict):
        errors.append("'test_data' must be an object when present.")

    return errors
# endregion


# region entry point
def main():
    parser = argparse.ArgumentParser(description="Validate a candidate TC JSON (hard-fail gate).")
    parser.add_argument("path", nargs="?", help="Path to the TC JSON file.")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from stdin.")
    args = parser.parse_args()

    if args.stdin:
        raw = sys.stdin.read()
    elif args.path:
        try:
            with open(args.path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            print(f"BLOCKED - cannot read file: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        print("BLOCKED - provide a file path or use --stdin.", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"BLOCKED - invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    errors = validate(data)
    if errors:
        print("BLOCKED - the candidate JSON did not pass validation:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print("OK - JSON is valid. Safe to create the folder and write.")
    sys.exit(0)


if __name__ == "__main__":
    main()
# endregion
