"""
==============================================================================
  dashboard/build_dashboard.py  —  READ-ONLY Suite Dashboard builder (v2)
==============================================================================
Scans the project's runs/ folder, reads every Report/result.json AND (for
failures) the Logs/ bundle, then writes ONE self-contained dashboard.html:
all data + styling + JS embedded inline. No server, no internet, no deps.

v2 features:
  * Modern design system + DARK/LIGHT toggle (persisted in localStorage)
  * Pass-rate donut (SVG) + pass-rate TREND sparkline (SVG)
  * Failure-category bar chart (SVG)
  * Flaky-tests spotlight
  * L2 LOG DRAWER: click a failing row -> slide-out panel showing the rendered
    summary.md, category, console errors, failed requests, and the failing
    screenshot — all embedded (no navigation needed)
  * Search + filter (verdict, flaky-only) + sortable table + per-test history

READ-ONLY: only READS result.json / Logs / screenshots and WRITES dashboard.html.
AUTO (A2): conftest.py calls build() at the end of each pytest session.
Manual:    python dashboard/build_dashboard.py
==============================================================================
"""

import json
from pathlib import Path
from datetime import datetime

DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent
RUNS_DIR = PROJECT_ROOT / "runs"
OUTPUT = DASHBOARD_DIR / "dashboard.html"


# --------------------------------------------------------------------------- #
#  1) Collect: read result.json (+ Logs bundle for failures)                  #
# --------------------------------------------------------------------------- #
def collect(runs_dir: Path = RUNS_DIR):
    records = []
    if not runs_dir.exists():
        return records

    for run_folder in sorted(runs_dir.glob("TC_*")):
        result = run_folder / "Report" / "result.json"
        if not result.exists():
            continue
        try:
            data = json.loads(result.read_text(encoding="utf-8"))
        except Exception:
            continue

        totals = data.get("totals", {}) or {}
        rel = run_folder.name

        def link(sub):
            p = run_folder / sub
            return f"../runs/{rel}/{sub}" if p.exists() else ""

        rec = {
            "folder": rel,
            "id": str(data.get("id", "?")),
            "title": str(data.get("title", "")),
            "verdict": str(data.get("verdict", "UNKNOWN")).upper(),
            "started_at": data.get("started_at", ""),
            "finished_at": data.get("finished_at", ""),
            "duration_s": int(data.get("duration_s", 0) or 0),
            "total": int(totals.get("total", 0) or 0),
            "passed": int(totals.get("passed", 0) or 0),
            "failed": int(totals.get("failed", 0) or 0),
            "report": link("Report/report.html"),
            "video": link(f"Video/{_video_name(run_folder)}"),
            "script": _first(run_folder / "Automation", "test_*.py", rel, "Automation"),
            "locators": link("Automation/locators.json"),
            # log fields (filled below only when a failure bundle exists)
            "fail_category": "", "log_summary_md": "", "log_summary_link": "",
            "console_errors": [], "failed_requests": [],
            "fail_step": None, "fail_url": "", "fail_shot": "", "error_msg": "",
        }
        _attach_logs(run_folder, rel, rec)
        records.append(rec)

    records.sort(key=lambda r: (r["finished_at"], r["folder"]), reverse=True)
    return records


def _attach_logs(run_folder: Path, rel: str, rec: dict):
    logs = run_folder / "Logs"
    if not logs.exists():
        return
    # summary.md (embedded for the drawer)
    smd = logs / "summary.md"
    if smd.exists():
        try:
            rec["log_summary_md"] = smd.read_text(encoding="utf-8")[:20000]
            rec["log_summary_link"] = f"../runs/{rel}/Logs/summary.md"
        except Exception:
            pass
    # first step_*.error.json (category + console + network + screenshot)
    for f in sorted(logs.glob("step_*.error.json")):
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rec["fail_category"] = e.get("category", "")
        rec["console_errors"] = (e.get("console_errors") or [])[:30]
        rec["failed_requests"] = (e.get("failed_requests") or [])[:30]
        rec["fail_step"] = e.get("step")
        rec["fail_url"] = e.get("url_at_failure", "")
        rec["error_msg"] = (e.get("message", "") or "").splitlines()[0][:400] if e.get("message") else ""
        step = e.get("step")
        if step is not None:
            shot = run_folder / "Screenshots" / f"step_{int(step):02d}.png"
            if shot.exists():
                rec["fail_shot"] = f"../runs/{rel}/Screenshots/step_{int(step):02d}.png"
        break


def _video_name(run_folder: Path):
    vdir = run_folder / "Video"
    if vdir.exists():
        webms = list(vdir.glob("*.webm"))
        if webms:
            return webms[0].name
    return "run.webm"


def _first(folder: Path, pattern: str, rel: str, sub: str):
    if folder.exists():
        hits = list(folder.glob(pattern))
        if hits:
            return f"../runs/{rel}/{sub}/{hits[0].name}"
    return ""


# --------------------------------------------------------------------------- #
#  2) Aggregate: KPIs, categories, flaky, pass-rate trend                     #
# --------------------------------------------------------------------------- #
def aggregate(records):
    total_runs = len(records)
    by_id = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)

    latest = [runs[0] for runs in by_id.values()]
    latest.sort(key=lambda r: (r["finished_at"], r["folder"]), reverse=True)

    passed = sum(1 for r in latest if r["verdict"] == "PASS")
    failed = sum(1 for r in latest if r["verdict"] == "FAIL")
    blocked = sum(1 for r in latest if r["verdict"] == "BLOCKED")
    pass_rate = round(100 * passed / len(latest)) if latest else 0
    avg_dur = round(sum(r["duration_s"] for r in latest) / len(latest), 1) if latest else 0

    flaky_ids = []
    for tid, runs in by_id.items():
        vs = {x["verdict"] for x in runs}
        if "PASS" in vs and ("FAIL" in vs or "BLOCKED" in vs):
            flaky_ids.append(tid)

    cats = {}
    for r in latest:
        if r["verdict"] != "PASS" and r["fail_category"]:
            cats[r["fail_category"]] = cats.get(r["fail_category"], 0) + 1

    # pass-rate trend: chronological order, cumulative pass-rate over all runs
    chrono = sorted(records, key=lambda r: (r["finished_at"], r["folder"]))
    trend, p = [], 0
    for i, r in enumerate(chrono, 1):
        if r["verdict"] == "PASS":
            p += 1
        trend.append(round(100 * p / i))
    trend = trend[-30:]  # last 30 points

    kpis = {
        "test_cases": len(by_id), "total_runs": total_runs,
        "passed": passed, "failed": failed, "blocked": blocked,
        "pass_rate": pass_rate, "avg_dur": avg_dur,
        "flaky": len(flaky_ids), "categories": cats, "trend": trend,
        "latest_run": latest[0]["finished_at"] if latest else "—",
    }
    return kpis, latest, by_id, flaky_ids


# --------------------------------------------------------------------------- #
#  3) Render                                                                  #
# --------------------------------------------------------------------------- #
def render(records):
    kpis, latest, by_id, flaky_ids = aggregate(records)
    payload = json.dumps({"kpis": kpis, "latest": latest, "by_id": by_id,
                          "flaky_ids": flaky_ids}, ensure_ascii=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe = payload.replace("</", "<\\/")  # cannot break out of <script>
    return _TEMPLATE.replace("/*__DATA__*/", safe).replace("__GENERATED__", generated)


def build(runs_dir: Path = RUNS_DIR, output: Path = OUTPUT):
    try:
        records = collect(runs_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render(records), encoding="utf-8")
        return output
    except Exception:
        return None  # a dashboard build must NEVER crash a test run


# =========================================================================== #
#  The self-contained HTML template (design system + SVG charts + drawer JS)  #
# =========================================================================== #
_TEMPLATE = r"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Suite Dashboard</title>
<style>
  :root{
    --bg:#eef2f7; --panel:#ffffff; --panel2:#f8fafc; --text:#0f172a; --muted:#64748b;
    --border:#e2e8f0; --accent:#4f46e5; --accent2:#6366f1;
    --pass:#16a34a; --fail:#dc2626; --block:#d97706; --shadow:0 10px 30px rgba(15,23,42,.08);
  }
  html[data-theme="dark"]{
    --bg:#0b1220; --panel:#111a2e; --panel2:#0e1728; --text:#e6edf7; --muted:#93a2b8;
    --border:#1e2b45; --accent:#818cf8; --accent2:#a5b4fc;
    --pass:#22c55e; --fail:#f87171; --block:#fbbf24; --shadow:0 10px 30px rgba(0,0,0,.45);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font-family:Segoe UI,system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
    transition:background .25s,color .25s}
  .wrap{max-width:1280px;margin:0 auto;padding:22px}
  /* header */
  .top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;
    position:sticky;top:0;z-index:20;background:linear-gradient(var(--bg),var(--bg) 70%,transparent);
    padding:6px 0 12px}
  .brand{display:flex;align-items:center;gap:12px}
  .brand .logo{width:40px;height:40px;border-radius:11px;display:grid;place-items:center;
    background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;font-size:20px;
    box-shadow:var(--shadow)}
  h1{margin:0;font-size:1.4rem;letter-spacing:.2px}
  .sub{color:var(--muted);font-size:.82rem}
  .top-actions{display:flex;gap:10px;align-items:center}
  .btn{border:1px solid var(--border);background:var(--panel);color:var(--text);
    padding:8px 12px;border-radius:10px;cursor:pointer;font-size:.85rem;display:inline-flex;
    gap:7px;align-items:center;transition:transform .06s,border-color .2s}
  .btn:hover{border-color:var(--accent)} .btn:active{transform:translateY(1px)}
  /* grid */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:6px 0 16px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:18px;
    box-shadow:var(--shadow)}
  .kpi b{display:block;font-size:1.75rem;line-height:1.05}
  .kpi span{color:var(--muted);font-size:.82rem}
  .row2{display:grid;grid-template-columns:1.1fr 1fr;gap:16px;margin-bottom:16px}
  @media(max-width:820px){.row2{grid-template-columns:1fr}}
  .card h2{margin:0 0 12px;font-size:1.02rem;display:flex;align-items:center;gap:8px}
  .center{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
  /* donut */
  .donut-num{font-size:1.5rem;font-weight:800}
  .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.83rem;color:var(--muted)}
  .dotc{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:middle}
  /* bars */
  .bar{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:.85rem}
  .bar .lab{width:150px;color:var(--muted)} .bar .track{flex:1;height:12px;background:var(--panel2);
    border:1px solid var(--border);border-radius:8px;overflow:hidden}
  .bar .fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2))}
  .bar .num{width:26px;text-align:right;font-weight:700}
  /* toolbar + table */
  .toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
  input[type=search],select{padding:9px 12px;border:1px solid var(--border);border-radius:10px;
    font-size:.9rem;background:var(--panel);color:var(--text)}
  input[type=search]{flex:1;min-width:220px}
  .chk{display:flex;align-items:center;gap:6px;font-size:.85rem;color:var(--muted);cursor:pointer;user-select:none}
  table{width:100%;border-collapse:collapse}
  th,td{padding:11px 10px;text-align:left;font-size:.9rem;vertical-align:middle;border-bottom:1px solid var(--border)}
  th{color:var(--muted);font-weight:600;cursor:pointer;user-select:none;position:sticky;top:64px;background:var(--panel)}
  tbody tr{transition:background .12s} tbody tr:hover{background:var(--panel2)}
  .clickable{cursor:pointer}
  .badge{display:inline-block;padding:3px 11px;border-radius:999px;font-weight:800;font-size:.74rem;letter-spacing:.3px}
  .PASS{background:color-mix(in oklab,var(--pass) 18%,transparent);color:var(--pass)}
  .FAIL{background:color-mix(in oklab,var(--fail) 18%,transparent);color:var(--fail)}
  .BLOCKED{background:color-mix(in oklab,var(--block) 20%,transparent);color:var(--block)}
  .UNKNOWN{background:color-mix(in oklab,var(--muted) 18%,transparent);color:var(--muted)}
  .cat{display:inline-block;background:color-mix(in oklab,var(--accent) 15%,transparent);
    color:var(--accent);border-radius:7px;padding:2px 9px;font-size:.74rem;font-weight:700;margin:2px}
  .links a{margin-right:8px;text-decoration:none;font-size:1.02rem}
  .muted{color:var(--muted)}
  .hist{display:flex;gap:3px;flex-wrap:wrap}
  .dot{width:12px;height:12px;border-radius:3px}
  details summary{cursor:pointer;color:var(--accent);font-size:.82rem}
  .fail-row td:first-child{box-shadow:inset 3px 0 0 var(--fail)}
  .flake-row td:first-child{box-shadow:inset 3px 0 0 var(--block)}
  .empty{padding:44px;text-align:center;color:var(--muted)}
  .pill{font-size:.72rem;color:var(--muted);border:1px solid var(--border);border-radius:999px;padding:2px 9px}
  footer{color:var(--muted);font-size:.8rem;margin-top:12px;text-align:center}
  /* drawer */
  .scrim{position:fixed;inset:0;background:rgba(2,6,23,.5);opacity:0;pointer-events:none;
    transition:opacity .2s;z-index:40}
  .scrim.open{opacity:1;pointer-events:auto}
  .drawer{position:fixed;top:0;right:0;height:100%;width:min(560px,94vw);background:var(--panel);
    border-left:1px solid var(--border);box-shadow:-20px 0 50px rgba(0,0,0,.25);
    transform:translateX(100%);transition:transform .25s ease;z-index:50;overflow:auto}
  .drawer.open{transform:none}
  .drawer .dh{position:sticky;top:0;background:var(--panel);padding:16px 18px;border-bottom:1px solid var(--border);
    display:flex;align-items:center;justify-content:space-between;gap:10px}
  .drawer .db{padding:16px 18px}
  .sec{margin:14px 0}
  .sec h3{margin:0 0 8px;font-size:.9rem;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
  .kv{font-size:.88rem;margin:4px 0} .kv b{color:var(--muted);font-weight:600}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.8rem}
  .box{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px 12px}
  .box.err{border-color:color-mix(in oklab,var(--fail) 40%,var(--border))}
  .shot{width:100%;border-radius:10px;border:1px solid var(--border)}
  .md h1,.md h2{font-size:1rem;margin:.6em 0 .3em}.md ul{margin:.3em 0 .3em 1.1em}.md code{background:var(--panel2);padding:1px 5px;border-radius:5px}
  .x{cursor:pointer;font-size:1.3rem;line-height:1;color:var(--muted);border:none;background:none}
</style></head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="logo">🧪</div>
      <div><h1>Test Suite Dashboard</h1>
        <div class="sub">Read-only · offline · built <b>__GENERATED__</b></div></div>
    </div>
    <div class="top-actions">
      <button class="btn" id="cmd">📋 cd runs &amp;&amp; python -m pytest</button>
      <button class="btn" id="theme">🌙 Dark</button>
    </div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="row2">
    <div class="card"><h2>📈 Pass-rate trend</h2><div id="trend"></div></div>
    <div class="card"><h2>🧭 Failure categories</h2><div id="cats"></div></div>
  </div>

  <div class="card" id="flakeCard" style="display:none">
    <h2>⚡ Flaky spotlight</h2><div id="flakes"></div>
  </div>

  <div class="card">
    <h2>📋 Test cases <span class="pill" id="count"></span></h2>
    <div class="toolbar">
      <input type="search" id="q" placeholder="Search by ID or title…  (press /)">
      <select id="vf"><option value="">All verdicts</option><option>PASS</option><option>FAIL</option><option>BLOCKED</option></select>
      <label class="chk"><input type="checkbox" id="ff"> Flaky only</label>
      <span class="muted" style="font-size:.8rem">Tip: click a failing row for its log</span>
    </div>
    <table id="tbl"><thead><tr>
      <th data-k="verdict">Verdict</th><th data-k="id">ID</th><th data-k="title">Title</th>
      <th data-k="finished_at">Last run</th><th data-k="duration_s">Dur</th>
      <th data-k="passed">Steps</th><th>Links</th><th>History</th>
    </tr></thead><tbody id="rows"></tbody></table>
    <div class="empty" id="empty" style="display:none">No runs yet. Run a test, then refresh.</div>
  </div>

  <footer>Self-contained · read-only · never modifies run data.</footer>
</div>

<!-- L2 log drawer -->
<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer" aria-hidden="true">
  <div class="dh">
    <div><span class="badge" id="dBadge"></span> <b id="dTitle" style="margin-left:6px"></b></div>
    <button class="x" id="dClose">×</button>
  </div>
  <div class="db" id="dBody"></div>
</aside>

<script>
const DATA = /*__DATA__*/;
const K=DATA.kpis, LATEST=DATA.latest, BYID=DATA.by_id, FLAKY=new Set(DATA.flaky_ids);
const $=s=>document.querySelector(s);
function esc(s){return (s==null?"":String(s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function fmt(s){return s? String(s).replace("T"," ").slice(0,16):"—"}

/* ---------- theme ---------- */
const root=document.documentElement, tBtn=$("#theme");
function setTheme(t){root.setAttribute("data-theme",t);tBtn.textContent=t==="dark"?"☀️ Light":"🌙 Dark";
  try{localStorage.setItem("mv_theme",t)}catch(e){}}
setTheme((()=>{try{return localStorage.getItem("mv_theme")||"light"}catch(e){return "light"}})());
tBtn.onclick=()=>setTheme(root.getAttribute("data-theme")==="dark"?"light":"dark");

/* ---------- copy command ---------- */
$("#cmd").onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText("cd runs && python -m pytest");
  const b=$("#cmd");const t=b.textContent;b.textContent="✅ Copied";setTimeout(()=>b.textContent=t,1200)};

/* ---------- KPIs + donut ---------- */
function donut(pct){
  const R=42,C=2*Math.PI*R,off=C*(1-pct/100);
  return `<svg width="104" height="104" viewBox="0 0 104 104">
    <circle cx="52" cy="52" r="${R}" fill="none" stroke="var(--border)" stroke-width="12"/>
    <circle cx="52" cy="52" r="${R}" fill="none" stroke="var(--pass)" stroke-width="12"
      stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${off}"
      transform="rotate(-90 52 52)"/>
    <text x="52" y="58" text-anchor="middle" class="donut-num" fill="var(--text)">${pct}%</text></svg>`;
}
function kpi(v,l){return `<div class="card kpi"><b>${v}</b><span>${l}</span></div>`}
$("#kpis").innerHTML =
  `<div class="card kpi center">${donut(K.pass_rate)}<div><b>${K.passed}/${K.test_cases}</b>
     <span>Passing (latest)</span></div></div>`+
  kpi(K.test_cases,"Test cases")+kpi(K.total_runs,"Total runs")+
  kpi(K.failed+K.blocked,"Failing / blocked")+kpi(K.flaky,"Flaky")+kpi(K.avg_dur+"s","Avg duration");

/* ---------- trend sparkline ---------- */
(function(){
  const t=K.trend||[]; const el=$("#trend");
  if(!t.length){el.innerHTML='<div class="muted">Not enough runs yet.</div>';return;}
  const W=520,H=120,pad=8,max=100,min=0;
  const xs=(i)=>pad+i*(W-2*pad)/Math.max(1,t.length-1);
  const ys=(v)=>H-pad-(v-min)/(max-min)*(H-2*pad);
  let d="",area="";
  t.forEach((v,i)=>{const x=xs(i),y=ys(v);d+=(i?"L":"M")+x+" "+y+" ";});
  area=`M${xs(0)} ${H-pad} `+t.map((v,i)=>`L${xs(i)} ${ys(v)}`).join(" ")+` L${xs(t.length-1)} ${H-pad} Z`;
  const last=t[t.length-1];
  el.innerHTML=`<svg width="100%" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="max-height:140px">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="var(--accent)" stop-opacity=".35"/>
      <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
    <path d="${area}" fill="url(#g)"/>
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="${xs(t.length-1)}" cy="${ys(last)}" r="4" fill="var(--accent)"/>
   </svg>
   <div class="muted" style="font-size:.8rem">Cumulative pass-rate over the last ${t.length} runs · now <b>${last}%</b></div>`;
})();

/* ---------- category bars ---------- */
(function(){
  const c=K.categories||{}; const el=$("#cats");
  const entries=Object.entries(c).sort((a,b)=>b[1]-a[1]);
  if(!entries.length){el.innerHTML='<div class="muted">No failures 🎉</div>';return;}
  const max=Math.max(...entries.map(e=>e[1]));
  el.innerHTML=entries.map(([k,n])=>`<div class="bar">
     <span class="lab">${esc(k)}</span>
     <span class="track"><span class="fill" style="width:${Math.round(100*n/max)}%"></span></span>
     <span class="num">${n}</span></div>`).join("");
})();

/* ---------- flaky spotlight ---------- */
(function(){
  const ids=DATA.flaky_ids||[]; if(!ids.length)return;
  $("#flakeCard").style.display="block";
  $("#flakes").innerHTML=ids.map(id=>{
    const runs=BYID[id]||[];const latest=runs[0]||{};
    return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
      <b>${esc(id)}</b> <span class="muted">— ${esc(latest.title||"")}</span>
      <span style="float:right">${histDots(id)}</span></div>`;
  }).join("");
})();

/* ---------- history dots ---------- */
function histDots(id){
  const runs=(BYID[id]||[]).slice().reverse();
  return `<span class="hist">`+runs.map(x=>{
    const c=x.verdict==="PASS"?"var(--pass)":x.verdict==="FAIL"?"var(--fail)":"var(--block)";
    return `<span class="dot" title="${x.verdict} · ${fmt(x.finished_at)}" style="background:${c}"></span>`;
  }).join("")+`</span>`;
}
function links(r){
  let o="";
  if(r.report)o+=`<a href="${r.report}" title="Report" target="_blank" onclick="event.stopPropagation()">📄</a>`;
  if(r.video)o+=`<a href="${r.video}" title="Video" target="_blank" onclick="event.stopPropagation()">🎥</a>`;
  if(r.script)o+=`<a href="${r.script}" title="Script" target="_blank" onclick="event.stopPropagation()">🐍</a>`;
  if(r.locators)o+=`<a href="${r.locators}" title="Locators" target="_blank" onclick="event.stopPropagation()">🧭</a>`;
  if(r.log_summary_link)o+=`<a href="#" title="Failure log" onclick="event.stopPropagation();openDrawer('${r.folder}');return false">🪵</a>`;
  return o||'<span class="muted">—</span>';
}

/* ---------- table ---------- */
let sortK="finished_at",sortAsc=false;
const q=$("#q"),vf=$("#vf"),ff=$("#ff");
q.oninput=vf.onchange=ff.onchange=renderTable;
document.querySelectorAll("#tbl th[data-k]").forEach(th=>th.onclick=()=>{
  const k=th.dataset.k;sortAsc=(sortK===k)?!sortAsc:true;sortK=k;renderTable();});

function renderTable(){
  let rows=LATEST.slice();
  const term=q.value.toLowerCase(),vv=vf.value,flakyOnly=ff.checked;
  if(term)rows=rows.filter(r=>(r.id+" "+r.title).toLowerCase().includes(term));
  if(vv)rows=rows.filter(r=>r.verdict===vv);
  if(flakyOnly)rows=rows.filter(r=>FLAKY.has(r.id));
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];
    if(typeof x==="string"){x=x.toLowerCase();y=(y||"").toLowerCase()}
    return (x<y?-1:x>y?1:0)*(sortAsc?1:-1);});
  $("#count").textContent=`${rows.length} shown`;
  $("#empty").style.display=rows.length?"none":"block";
  $("#rows").innerHTML=rows.map(r=>{
    const hist=BYID[r.id]||[];
    const cls=(r.verdict!=="PASS"?"fail-row ":"")+(FLAKY.has(r.id)?"flake-row ":"");
    const canDrawer=!!r.log_summary_md;
    const more=hist.length>1?`<details onclick="event.stopPropagation()"><summary>${hist.length} runs</summary>
      ${hist.map(x=>`<div class="muted" style="padding:2px 0">
        <span class="badge ${x.verdict}">${x.verdict}</span> ${fmt(x.finished_at)} · ${x.passed}/${x.total} · ${x.duration_s}s
        ${x.report?`<a href="${x.report}" target="_blank">📄</a>`:""}</div>`).join("")}</details>`:"";
    return `<tr class="${cls}${canDrawer?"clickable":""}" ${canDrawer?`onclick="openDrawer('${r.folder}')"`:""}>
      <td><span class="badge ${r.verdict}">${r.verdict}</span>${FLAKY.has(r.id)?' <span class="cat">flaky</span>':''}</td>
      <td><b>${esc(r.id)}</b></td><td>${esc(r.title)}</td>
      <td>${fmt(r.finished_at)}</td><td>${r.duration_s}s</td><td>${r.passed}/${r.total}</td>
      <td class="links">${links(r)}</td><td>${histDots(r.id)}${more}</td></tr>`;
  }).join("");
}
renderTable();

/* ---------- L2 drawer ---------- */
const scrim=$("#scrim"),drawer=$("#drawer");
function closeDrawer(){drawer.classList.remove("open");scrim.classList.remove("open");drawer.setAttribute("aria-hidden","true")}
$("#dClose").onclick=closeDrawer; scrim.onclick=closeDrawer;
document.addEventListener("keydown",e=>{
  if(e.key==="Escape")closeDrawer();
  if(e.key==="/"&&document.activeElement!==q){e.preventDefault();q.focus()}
});
function mdToHtml(md){
  return esc(md)
    .replace(/^### (.*)$/gm,"<h3>$1</h3>").replace(/^## (.*)$/gm,"<h2>$1</h2>").replace(/^# (.*)$/gm,"<h1>$1</h1>")
    .replace(/^\s*-\s+(.*)$/gm,"<li>$1</li>").replace(/(<li>[\s\S]*?<\/li>)/g,"<ul>$1</ul>")
    .replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\*\*([^*]+)\*\*/g,"<b>$1</b>").replace(/\n{2,}/g,"<br><br>");
}
window.openDrawer=function(folder){
  const r=LATEST.find(x=>x.folder===folder)||Object.values(BYID).flat().find(x=>x.folder===folder);
  if(!r)return;
  $("#dBadge").className="badge "+r.verdict; $("#dBadge").textContent=r.verdict;
  $("#dTitle").textContent=`${r.id} — ${r.title}`;
  const con=r.console_errors||[],net=r.failed_requests||[];
  const conHtml=con.length?con.map(c=>`<div class="box err mono">[${esc(c.type||"?")}] ${esc(c.text||"")}</div>`).join(""):'<div class="muted">None</div>';
  const netHtml=net.length?net.map(n=>`<div class="box err mono">${esc(n.status||"?")} — ${esc(n.url||"")}</div>`).join(""):'<div class="muted">None</div>';
  $("#dBody").innerHTML=`
    ${r.fail_category?`<span class="cat">${esc(r.fail_category)}</span>`:""}
    ${r.fail_step!=null?`<span class="pill">Failed at step ${r.fail_step}</span>`:""}
    ${r.error_msg?`<div class="sec"><div class="box err mono">${esc(r.error_msg)}</div></div>`:""}
    ${r.fail_url?`<div class="kv"><b>URL:</b> <span class="mono">${esc(r.fail_url)}</span></div>`:""}
    ${r.fail_shot?`<div class="sec"><h3>Screenshot at failure</h3><a href="${r.fail_shot}" target="_blank"><img class="shot" src="${r.fail_shot}"></a></div>`:""}
    <div class="sec"><h3>Summary</h3><div class="box md">${r.log_summary_md?mdToHtml(r.log_summary_md):'<span class="muted">No summary.md</span>'}</div></div>
    <div class="sec"><h3>Console errors (${con.length})</h3>${conHtml}</div>
    <div class="sec"><h3>Failed requests (${net.length})</h3>${netHtml}</div>
    <div class="sec links" style="font-size:1.1rem">
      ${r.report?`<a href="${r.report}" target="_blank" title="Full report">📄 Report</a>`:""}
      ${r.video?`<a href="${r.video}" target="_blank" title="Video">🎥 Video</a>`:""}
      ${r.log_summary_link?`<a href="${r.log_summary_link}" target="_blank" title="Raw summary.md">🪵 Raw log</a>`:""}
    </div>`;
  drawer.classList.add("open");scrim.classList.add("open");drawer.setAttribute("aria-hidden","false");
};
</script>
</body></html>"""


if __name__ == "__main__":
    out = build()
    print(f"Dashboard written: {out}" if out else "Dashboard build skipped.")
