"""
==============================================================================
  conftest.py  —  THE WHOLE ENGINE IN ONE FILE
==============================================================================
  * CONFIG    (CFG — loaded ENTIRELY from .env; nothing hard-coded; also a fixture)
  * REPORTER  (collects steps, writes report.html + result.json)
  * FAIL LOGS (on failure only -> Logs/run.log + step_NN.error.json + summary.md)
  * FIXTURES  (CFG + video + timeouts + console/network capture + the `reporter`)
  * HELPERS   (save_locator_map -> Automation/locators.json)

A generated test uses the fixtures directly in its signature:
    def test_<ID>(page, CFG, reporter):

Fixes baked in:
  * Config   -> everything comes from .env (edit .env, never the code).
  * Video    -> recorded natively into the run's Video/ folder.
  * Hanging  -> timeouts bound every action; a stuck step fails, never forever.
  * Fail shot-> full-page on failure, height-capped so it's never huge.
  * Logs     -> ONLY on failure, a diagnostic bundle is written into Logs/.
==============================================================================
"""

import os
import json
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import Page  # noqa: F401  (handy for generated tests)

# --- Load .env (the single source of configuration) --------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    # If python-dotenv isn't installed, real environment variables still work.
    pass


def _get(key, default=""):
    return os.getenv(key, default)


def _int(key, default):
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _bool(key, default=False):
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ============================================================================
#  1) CONFIG  —  loaded from .env.  The single source of settings.
# ============================================================================
CFG = {
    "base_url":   _get("MV_BASE_URL", "https://example.com"),

    "browser":    _get("MV_BROWSER", "chromium"),   # chromium | firefox | webkit
    "headless":   _bool("MV_HEADLESS", False),
    "viewport":   {"width": _int("MV_VIEWPORT_W", 1440),
                   "height": _int("MV_VIEWPORT_H", 900)},

    "t_action":   _int("MV_T_ACTION", 15000),
    "t_nav":      _int("MV_T_NAV", 30000),
    "t_expect":   _int("MV_T_EXPECT", 10000),
    "wait_until": _get("MV_WAIT_UNTIL", "load"),

    "video":      _bool("MV_VIDEO", True),
    "video_name": _get("MV_VIDEO_NAME", "run.webm"),

    "fail_shot_max_h": _int("MV_FAIL_SHOT_MAX_H", 2400),

    # Failure-log caps (logs are written ONLY on failure)
    "log_max_console": _int("MV_LOG_MAX_CONSOLE", 20),
    "log_max_network": _int("MV_LOG_MAX_NETWORK", 20),
    "log_max_tb_lines": _int("MV_LOG_MAX_TB_LINES", 15),
}

# Subfolders inside every run folder (Logs is created but stays empty on pass)
SUBS = ["Video", "Screenshots", "Report", "JSON", "Automation", "Logs"]
PROJECT_ROOT = Path(__file__).resolve().parent

# Caches so all fixtures for the SAME test resolve to the SAME folder.
_RUN_DIRS = {}          # tc_id -> Path
_ALL_RUN_DIRS = set()   # every folder touched this session (for video rename)


def _ensure(rd: Path) -> Path:
    for s in SUBS:
        (rd / s).mkdir(parents=True, exist_ok=True)
    _ALL_RUN_DIRS.add(rd)
    return rd


def run_dir(tc_id=None) -> Path:
    """The current test-case folder.
    * If TC_RUN_DIR is set (tc-runner flow) -> that exact folder, always.
    * Otherwise -> runs/<ID>/, ID-keyed (matches tc-converter), so a token-free
      pytest rerun writes video/screenshots/report back into the SAME folder
      instead of spawning a new timestamped one."""
    env = os.getenv("TC_RUN_DIR", "").strip()
    if env:
        rd = Path(env)
        if not rd.is_absolute():
            rd = PROJECT_ROOT / rd
        return _ensure(rd)

    key = str(tc_id or "RUN")
    if key not in _RUN_DIRS:
        rd = PROJECT_ROOT / "runs" / key
        _RUN_DIRS[key] = _ensure(rd)
    return _RUN_DIRS[key]


def save_locator_map(mapping: dict, tc_id=None) -> Path:
    """Persist the Observer-phase locator map to Automation/locators.json."""
    path = run_dir(tc_id) / "Automation" / "locators.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return path


# ============================================================================
#  FAILURE DIAGNOSTICS  —  classification + summary hints
# ============================================================================
CATEGORY_HINT = {
    "TIMEOUT": "The element never became actionable in time. A prior step may "
               "have left the page in the wrong state, a spinner/overlay never "
               "resolved, or the timeout (CFG t_action/t_expect) is too low.",
    "LOCATOR_NOT_FOUND": "The locator matched no element. The selector may be "
               "wrong or the UI changed. Re-observe the page and prefer "
               "role/label/text locators over brittle CSS/XPath.",
    "ASSERTION": "The expected condition was not met. Verify the expected result "
               "is correct and that the previous step produced the right state.",
    "NETWORK": "A network/navigation error occurred. Check connectivity, the "
               "base_url, or a failing backend request (see failed_requests).",
    "STEP_LOGIC": "A Python error in the step body (e.g., a bad test_data key or "
               "a wrong type). Fix the generated step code.",
    "UNKNOWN": "Unclassified error. Inspect the traceback plus the console and "
               "network details below.",
}


def _classify_failure(err_type: str, message: str) -> str:
    m = (message or "").lower()
    if any(s in m for s in ("net::err", "err_connection", "err_name_not_resolved",
                            "err_timed_out", "err_internet")):
        return "NETWORK"
    if err_type == "AssertionError":
        return "ASSERTION"      # an expect(...) condition was not met
    if err_type == "TimeoutError" or ("timeout" in m and "exceeded" in m):
        if "waiting for" in m and ("locator" in m or "get_by" in m or "selector" in m):
            return "LOCATOR_NOT_FOUND"
        return "TIMEOUT"
    if err_type in ("KeyError", "TypeError", "ValueError", "IndexError",
                    "AttributeError", "NameError"):
        return "STEP_LOGIC"
    return "UNKNOWN"


def _page_context(page):
    """URL + title at the moment of failure (best-effort; never raises)."""
    out = {"url": "", "title": ""}
    try:
        out["url"] = page.url
    except Exception:
        pass
    try:
        out["title"] = page.title()
    except Exception:
        pass
    return out


# ============================================================================
#  2) REPORTER  —  collects steps, writes report + (on failure) logs
# ============================================================================
class Reporter:
    def __init__(self, tc_id, title):
        self.tc_id, self.title = tc_id, title
        self.steps = []
        self.timeline = []          # every step (start/dur/result) for run.log
        self.started = datetime.now()
        self.run = run_dir(tc_id)
        self.shots = self.run / "Screenshots"

    # ---- screenshots ---------------------------------------------------------
    def _shot(self, page, num, on_fail=False):
        """Normal screenshot on pass; on failure a full-page shot capped to
        CFG['fail_shot_max_h'] so long pages don't produce a giant image."""
        path = str(self.shots / f"step_{num:02d}.png")
        try:
            if on_fail:
                try:
                    h = int(page.evaluate("document.body.scrollHeight"))
                except Exception:
                    h = CFG["viewport"]["height"]
                capped = min(h, CFG["fail_shot_max_h"])
                page.screenshot(path=path, clip={
                    "x": 0, "y": 0,
                    "width": CFG["viewport"]["width"], "height": capped})
            else:
                page.screenshot(path=path)
        except Exception:
            pass

    # ---- the step wrapper ----------------------------------------------------
    @contextmanager
    def step(self, page, num, action, expected):
        """Wrap ONE step. On success -> screenshot + pass. On error (incl.
        timeout) -> capped screenshot + fail + a Logs/ diagnostic bundle, then
        re-raise so the test stops (stop-on-first-failure)."""
        rec = {"step": num, "action": action, "expected": expected,
               "actual": "", "result": "pass",
               "screenshot": f"Screenshots/step_{num:02d}.png"}
        start = datetime.now()
        try:
            yield
            self._shot(page, num, on_fail=False)
            rec["actual"] = "Completed as expected."
        except Exception as exc:
            dur = int((datetime.now() - start).total_seconds() * 1000)
            self._shot(page, num, on_fail=True)
            rec["result"] = "fail"
            rec["actual"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            self.timeline.append({"step": num, "action": action,
                                  "expected": expected, "result": "fail",
                                  "duration_ms": dur})
            self.steps.append(rec)
            try:
                self._log_failure(page, num, action, expected, exc, dur)
            except Exception:
                pass  # logging must NEVER mask the real failure
            raise
        dur = int((datetime.now() - start).total_seconds() * 1000)
        self.timeline.append({"step": num, "action": action,
                              "expected": expected, "result": "pass",
                              "duration_ms": dur})
        self.steps.append(rec)

    # ---- failure logging (ONLY on failure) -----------------------------------
    def _log_failure(self, page, num, action, expected, exc, dur_ms):
        logs = self.run / "Logs"
        logs.mkdir(parents=True, exist_ok=True)

        err_type = type(exc).__name__
        message = str(exc)
        category = _classify_failure(err_type, message)
        ctx = _page_context(page)
        console = list(getattr(page, "_mv_console", []))[-CFG["log_max_console"]:]
        network = list(getattr(page, "_mv_network", []))[-CFG["log_max_network"]:]
        tb = traceback.format_exc()
        tb_tail = "".join(tb.splitlines(keepends=True)[-CFG["log_max_tb_lines"]:])
        first_line = message.strip().splitlines()[0] if message.strip() else ""

        record = {
            "tc_id": self.tc_id,
            "title": self.title,
            "step": num,
            "category": category,
            "action": action,
            "expected": expected,
            "error_type": err_type,
            "message": message[:1000],
            "url_at_failure": ctx["url"],
            "page_title": ctx["title"],
            "console_errors": console,
            "failed_requests": network,
            "duration_ms": dur_ms,
            "traceback_tail": tb_tail,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        # 1) structured, machine-readable record
        (logs / f"step_{num:02d}.error.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

        # 2) full timeline of the run up to the failure
        (logs / "run.log").write_text(
            self._timeline_text(record, first_line), encoding="utf-8")

        # 3) human-readable summary (mechanical baseline; the AI enriches this
        #    during a live tc-runner session)
        (logs / "summary.md").write_text(
            _summary_md(record, first_line), encoding="utf-8")

        return record

    def _timeline_text(self, record, first_line):
        L = []
        L.append(f"==== RUN LOG — {self.tc_id} : {self.title} ====")
        L.append(f"Browser: {CFG['browser']} | viewport "
                 f"{CFG['viewport']['width']}x{CFG['viewport']['height']} | "
                 f"base_url {CFG['base_url']}")
        L.append(f"Started : {self.started.isoformat(timespec='seconds')}")
        L.append("")
        L.append("Timeline:")
        for e in self.timeline:
            L.append(f"  Step {e['step']:02d} | {e['result'].upper():4} | "
                     f"{e['duration_ms']:>6}ms | {e['action']}")
            if e["result"] == "fail":
                L.append(f"           └─ expected: {e['expected']}")
        L.append("")
        L.append(f"FAILURE at Step {record['step']}: {record['category']}")
        L.append(f"  {record['error_type']}: {first_line}")
        L.append(f"  URL   : {record['url_at_failure']}  (title: {record['page_title']})")
        L.append(f"  Console errors : {len(record['console_errors'])}")
        L.append(f"  Failed requests: {len(record['failed_requests'])}")
        L.append("")
        L.append("Traceback (tail):")
        L.append(record["traceback_tail"].rstrip())
        return "\n".join(L) + "\n"


def _summary_md(record, first_line):
    cat = record["category"]
    hint = CATEGORY_HINT.get(cat, "")
    con = record["console_errors"]
    net = record["failed_requests"]
    con_lines = "\n".join(f"  - [{c.get('type','?')}] {c.get('text','')}" for c in con) or "  (none)"
    net_lines = "\n".join(f"  - {n.get('status','?')} {n.get('url','')}" for n in net) or "  (none)"
    n = record["step"]
    return f"""# Failure Summary — {record['tc_id']}

**Failed at:** Step {n} — "{record['action']}"
**Category:** {cat}
**Error:** `{record['error_type']}: {first_line}`

## What happened
- **Expected:** {record['expected']}
- **URL at failure:** {record['url_at_failure']}
- **Page title:** {record['page_title']}
- **Step duration:** {record['duration_ms']} ms

## Likely cause
{hint}

## Console errors (last {len(con)})
{con_lines}

## Failed network requests (last {len(net)})
{net_lines}

## Evidence
- Screenshot: `../Screenshots/step_{n:02d}.png`
- Structured record: `step_{n:02d}.error.json`
- Full timeline: `run.log`

---
> _Auto-generated baseline. During a live **tc-runner** session, the AI agent
> refines this summary with a specific root-cause diagnosis and a concrete fix._
"""


# ============================================================================
#  REPORT (result.json + report.html)
# ============================================================================
class _ReportMixin:
    pass


def _finalize(rep: "Reporter"):
    done = datetime.now()
    passed = sum(s["result"] == "pass" for s in rep.steps)
    failed = sum(s["result"] == "fail" for s in rep.steps)
    verdict = "PASS" if failed == 0 and passed > 0 else "FAIL"
    result = {
        "id": rep.tc_id, "title": rep.title, "verdict": verdict,
        "started_at": rep.started.isoformat(timespec="seconds"),
        "finished_at": done.isoformat(timespec="seconds"),
        "duration_s": int((done - rep.started).total_seconds()),
        "totals": {"total": len(rep.steps), "passed": passed, "failed": failed},
        "steps": rep.steps,
    }
    r = rep.run / "Report"
    r.mkdir(parents=True, exist_ok=True)
    (r / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (r / "report.html").write_text(_html(result), encoding="utf-8")
    return result


# attach finalize as a method
Reporter.finalize = lambda self: _finalize(self)


def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _html(r):
    """Self-contained HTML report (template is inline — no extra files)."""
    v = r["verdict"]
    color = {"PASS": "#16a34a", "FAIL": "#dc2626"}.get(v, "#d97706")
    rows = ""
    for s in r["steps"]:
        c = "#dcfce7" if s["result"] == "pass" else "#fee2e2"
        tc = "#166534" if s["result"] == "pass" else "#991b1b"
        rows += (
            f'<tr><td>{s["step"]}</td><td>{_esc(s["action"])}</td>'
            f'<td>{_esc(s["expected"])}</td><td>{_esc(s["actual"])}</td>'
            f'<td><b style="color:{tc};background:{c};padding:3px 8px;'
            f'border-radius:6px">{s["result"].capitalize()}</b></td>'
            f'<td><a href="../{s["screenshot"]}"><img src="../{s["screenshot"]}" '
            f'style="max-width:160px;border:1px solid #ccc;border-radius:4px"></a></td></tr>')
    t = r["totals"]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{r['id']} Report</title><style>
body{{font-family:Segoe UI,system-ui,sans-serif;background:#f4f7fb;margin:0;padding:24px;color:#1f2937}}
.card{{background:#fff;border:1px solid #dce4ee;border-radius:12px;padding:20px;margin:0 auto 18px;max-width:1100px;box-shadow:0 8px 24px rgba(15,23,42,.06)}}
h1{{margin:0;font-size:1.5rem}} .badge{{color:#fff;background:{color};padding:6px 14px;border-radius:999px;font-weight:700;float:right}}
table{{width:100%;border-collapse:collapse;margin-top:10px}} th,td{{border:1px solid #e5e7eb;padding:9px;text-align:left;vertical-align:top}}
th{{background:#f8fafc}} video{{width:100%;max-width:880px;border-radius:10px;border:1px solid #ccc}}
.m{{display:inline-block;background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:10px 16px;margin:6px 6px 0 0}}
</style></head><body>
<div class="card"><span class="badge">{v}</span>
<h1>{r['id']} — {_esc(r['title'])}</h1>
<p style="color:#64748b">{CFG['browser']} · viewport {CFG['viewport']['width']}x{CFG['viewport']['height']}</p>
<div><span class="m"><b>{t['total']}</b> Steps</span><span class="m"><b>{t['passed']}</b> Passed</span>
<span class="m"><b>{t['failed']}</b> Failed</span><span class="m"><b>{r['duration_s']}s</b> Duration</span></div></div>
<div class="card"><h2>Execution Steps</h2><table>
<tr><th>#</th><th>Action</th><th>Expected</th><th>Actual</th><th>Status</th><th>Evidence</th></tr>
{rows}</table></div>
<div class="card"><h2>Video</h2>
<video controls src="../Video/{CFG['video_name']}"></video>
<p><a href="../Video/{CFG['video_name']}">Download video</a></p></div>
<div class="card" style="color:#64748b">Generated {r['finished_at']}</div>
</body></html>"""


# ============================================================================
#  3) PYTEST FIXTURES  —  CFG + video + timeouts + console/network + reporter
# ============================================================================
@pytest.fixture(name="CFG")
def _cfg_fixture():
    """Expose the CFG dict to tests via their signature: (page, CFG, reporter)."""
    return CFG


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, "headless": CFG["headless"]}


@pytest.fixture
def browser_context_args(browser_context_args, request):
    args = {**browser_context_args, "viewport": CFG["viewport"]}
    if CFG["video"]:                                   # VIDEO FIX
        tc_id = _marker(request, "tc_id")
        vdir = run_dir(tc_id) / "Video"
        vdir.mkdir(parents=True, exist_ok=True)
        args["record_video_dir"] = str(vdir)
        args["record_video_size"] = CFG["viewport"]
    return args


@pytest.fixture
def page(page):
    # Timeouts (never hang forever)
    page.set_default_timeout(CFG["t_action"])
    page.set_default_navigation_timeout(CFG["t_nav"])

    # Diagnostic collectors — used ONLY if a step later fails. Stashed on the
    # page so Reporter can read them at failure time.
    console_msgs, failed_reqs = [], []

    def _on_console(msg):
        try:
            if msg.type in ("error", "warning") and len(console_msgs) < 200:
                console_msgs.append({"type": msg.type, "text": (msg.text or "")[:500]})
        except Exception:
            pass

    def _on_response(resp):
        try:
            if resp.status >= 400 and len(failed_reqs) < 200:
                failed_reqs.append({"status": resp.status, "url": (resp.url or "")[:300]})
        except Exception:
            pass

    def _on_requestfailed(req):
        try:
            if len(failed_reqs) < 200:
                failed_reqs.append({"status": "failed", "url": (req.url or "")[:300],
                                    "error": str(getattr(req, "failure", "") or "")[:200]})
        except Exception:
            pass

    page.on("console", _on_console)
    page.on("response", _on_response)
    page.on("requestfailed", _on_requestfailed)
    page._mv_console = console_msgs
    page._mv_network = failed_reqs

    yield page


@pytest.fixture
def reporter(request):
    tc_id = _marker(request, "tc_id") or request.node.name.replace("test_", "")
    title = _marker(request, "tc_title") or request.node.name
    rep = Reporter(tc_id, title)
    yield rep
    rep.finalize()


def _marker(request, name):
    m = request.node.get_closest_marker(name)
    return m.args[0] if (m and m.args) else None


def pytest_sessionfinish(session, exitstatus):
    """End-of-session housekeeping: (1) rename each run's video to run.webm,
    (2) refresh the read-only Suite Dashboard (A2 auto-refresh)."""
    # (1) rename Playwright's random *.webm to run.webm in every run folder used
    if CFG["video"]:
        for rd in _ALL_RUN_DIRS:
            try:
                vdir = rd / "Video"
                webms = sorted(vdir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
                if webms and webms[-1].name != CFG["video_name"]:
                    target = vdir / CFG["video_name"]
                    if target.exists():
                        target.unlink()
                    webms[-1].rename(target)
            except Exception:
                pass

    # (2) A2 auto-refresh: rebuild dashboard/dashboard.html from all runs.
    # Read-only + wrapped so it can NEVER fail a test run.
    try:
        import sys
        sys.path.insert(0, str(PROJECT_ROOT / "dashboard"))
        from build_dashboard import build
        build()
    except Exception:
        pass


def pytest_configure(config):
    config.addinivalue_line("markers", "tc_id(id): the test case ID")
    config.addinivalue_line("markers", "tc_title(title): the test case title")
