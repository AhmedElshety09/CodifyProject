"""
==============================================================================
  example_test.py  —  THE CANONICAL TEMPLATE for every generated test
==============================================================================
This is the general, ideal shape of a pytest + Playwright (Python) test.
tc-runner MUST generate every `Automation/test_TC_<ID>.py` in THIS exact shape.
It is intentionally NOT tied to any specific website — it drives whatever
`CFG["base_url"]` (from .env) points at, and does one universal check so it
runs green against any URL as a smoke test.

MANDATORY CONVENTIONS (the runner copies all of these):
  1. Decorators  @pytest.mark.tc_id(...) / @pytest.mark.tc_title(...)
  2. Signature   def test_TC_<ID>(page, CFG, reporter):   (CFG comes from .env)
  3. Precondition line before the steps: page.goto(CFG["base_url"], ...)
  4. One  `with reporter.step(page, n, action, expected):`  block per step
  5. SEMANTIC locators captured live, in priority order:
        get_by_role / get_by_label / get_by_text / get_by_placeholder   (best)
        > get_by_test_id (data-testid)  >  #id / stable shallow CSS      (ok)
        avoid long XPath / deep CSS.
  6. Explicit expect(...) assertions using CFG["t_expect"].
==============================================================================
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.tc_id("EXAMPLE")
@pytest.mark.tc_title("Canonical template — smoke check that base_url loads")
def test_TC_EXAMPLE(page: Page, CFG, reporter):

    # --- Preconditions --------------------------------------------------------
    # If a test needs login, do it here using CFG (see the commented block at the
    # bottom). Otherwise just open the app under test.
    page.goto(CFG["base_url"], wait_until=CFG["wait_until"])

    # --- Steps: one reporter.step(...) block per JSON step --------------------
    with reporter.step(page, 1, "Open the application under test",
                       "The page loads and its body is visible"):
        # Universal assertion so the template is runnable against ANY base_url.
        expect(page.locator("body")).to_be_visible(timeout=CFG["t_expect"])

    # -------------------------------------------------------------------------
    # HOW A REAL GENERATED STEP LOOKS (semantic locators + smart assertions):
    #
    #   with reporter.step(page, 2, "Type 'John' in the Username field",
    #                      "The Username field contains 'John'"):
    #       page.get_by_label("Username").fill("John")
    #       expect(page.get_by_label("Username")).to_have_value("John")
    #
    #   with reporter.step(page, 3, "Click Submit",
    #                      "A success message is shown"):
    #       page.get_by_role("button", name="Submit").click()
    #       expect(page.get_by_text("Success")).to_be_visible(timeout=CFG["t_expect"])
    # -------------------------------------------------------------------------


# ===========================================================================
#  LOGIN PRECONDITION TEMPLATE (use when the JSON has a login precondition):
#
#   page.goto(CFG["base_url"], wait_until=CFG["wait_until"])
#   page.get_by_label("Username").fill(CFG["username"])
#   page.get_by_label("Password").fill(CFG["password"])
#   page.get_by_role("button", name="Sign in").click()
#   try:
#       expect(page.get_by_role("heading", name="Dashboard")).to_be_visible(
#           timeout=CFG["t_expect"])
#   except Exception:
#       pytest.skip("BLOCKED: could not reach the logged-in start state")
# ===========================================================================
