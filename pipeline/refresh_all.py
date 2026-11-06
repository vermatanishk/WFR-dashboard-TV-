"""
ONE entry point for the daily 7 pm refresh of EVERYTHING (owner, 2026-11-06: the refresh must not stop at the old tabs).

  python3 pipeline/refresh_all.py plan     what to pull from ClickHouse today (incremental ranges) + which gates are red
  python3 pipeline/refresh_all.py build    run every deterministic step in order (Zoho REST + builds + tests) and stop on the first failure
  python3 pipeline/refresh_all.py gates    freshness gates only (exit 1 if any layer is stale) - run this before every push

Incremental by design
  * Zoho tickets: pull_complaint_tickets.py re-reads only the last 3 days (older days are cached in cmp_zoho_tickets.json).
  * ClickHouse returns: 7-day files cmp_returns_<A>_<B>.json (B exclusive). Daily: pull everything not yet covered PLUS the trailing 28 days
    (statuses move: in progress -> refunded / rejected). Sundays: re-pull the whole 60-day window. Older files are never touched.
  * Warehouse comments: recheck_wh_comments.py reads only uncached or provisional (no_wh_comment / unrecognized) tickets.
  * Photos: only orders that have no read yet (damage_images.py), never re-read.
Steps that need the Claude session itself (ClickHouse MCP pulls, reading photos) are listed by `plan`; `gates` proves they were done.
"""
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
IST = timezone(timedelta(hours=5, minutes=30))
WINDOW = 60
TRAILING = 28
CHUNK = 7


def today():
    return datetime.now(IST).date()


def js(name):
    return json.loads((HERE / name).read_text())


# ------------------------------------------------------------------------------------------------ gates
def gates():
    """-> list of (layer, ok, message). `ok` False = stale / broken: do not ship."""
    t = today()
    out = []

    def chk(layer, ok, msg):
        out.append((layer, bool(ok), msg))

    # core dashboard (tabs 1-5)
    d = js("data.json")
    gen = datetime.strptime(d["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(IST).date()
    chk("core data.json", (t - gen).days <= 1, f"generated {gen}")
    # complaint layer
    try:
        sys.path.insert(0, str(HERE))
        from build_complaints import coverage, return_files
        files = return_files()
        first, end, gaps = coverage(files)
        chk("returns pull covers through yesterday", end >= t.isoformat() and not gaps, f"covered {first}..{end} (exclusive), gaps={gaps}")
    except SystemExit as e:
        chk("returns pull", False, str(e))
    z = json.loads((RAW / "cmp_zoho_tickets.json").read_text())
    chk("zoho complaint tickets", (t - datetime.strptime(z["pulled_at"], "%Y-%m-%dT%H:%M:%SZ").date()).days <= 1, f"pulled {z['pulled_at']}")
    e = js("complaints_export.json")
    chk("complaints_export.json", e["t2_cap_date"] >= (t - timedelta(days=2)).isoformat(), f"last complaint day {e['t2_cap_date']}")
    for name in ("cmp_wfr_trend.json", "cmp_damage_trend.json"):
        tr = js(name)
        chk(name, tr["t2_cutoff"] == e["t2_cap_date"], f"cutoff {tr['t2_cutoff']} vs export {e['t2_cap_date']}")
    chk("cmp_summary.json", js("cmp_summary.json")["window"][1] == e["t2_cap_date"], f"window {js('cmp_summary.json')['window']}")
    gaps = [r for r in e["rows"] if r[e["columns"].index("WH input")] == "Verdict not read (gap)"]
    chk("warehouse verdict gaps = 0", not gaps, f"{len(gaps)} tickets past T-2 without a read verdict")
    unread = sum(1 for r in e["rows"] if r[e["columns"].index("Photo bucket")] == "Photo not read yet"
                 and r[e["columns"].index("Created date")] >= (t - timedelta(days=30)).isoformat())
    chk("damage photos read (last 30 days)", unread == 0, f"{unread} orders still 'Photo not read yet'")
    # swap + rca feeds
    sw = js("swap_export.json")
    chk("order swap export", sw["t2_cap_date"] >= (t - timedelta(days=4)).isoformat(), f"through {sw['t2_cap_date']}")
    rc = js("rca_export.json")
    chk("RCA export (root-cause columns)", rc["t2_cap_date"] >= (t - timedelta(days=4)).isoformat(), f"through {rc['t2_cap_date']}")
    html = (HERE.parent / "index.html").read_text()
    chk("index.html contains the latest complaint day", f'"t2_cutoff": "{e["t2_cap_date"]}"' in html or e["t2_cap_date"] in html, "rebuild with build_html.py")
    return out


def print_gates(g):
    for layer, ok, msg in g:
        print(("OK   " if ok else "RED  ") + layer.ljust(44) + msg)
    bad = [x for x in g if not x[1]]
    print(f"\n{len(bad)} red gate(s)" if bad else "\nall gates green")
    return not bad


# ------------------------------------------------------------------------------------------------ plan
def plan():
    from build_complaints import coverage, return_files
    t = today()
    files = return_files()
    first, end, gaps = coverage(files)
    start = (t - timedelta(days=WINDOW)).isoformat()
    full = t.weekday() == 6                                  # Sunday: re-pull the whole window
    re_from = start if full else (t - timedelta(days=TRAILING)).isoformat()
    need_from = min(re_from, end)                            # also everything after the last covered day
    rng, cur = [], date.fromisoformat(max(need_from, start))
    stop = t                                                 # through yesterday: today is incomplete (and inside T-2 anyway)
    while cur < stop:
        nxt = min(cur + timedelta(days=CHUNK), stop)
        rng.append((cur.isoformat(), nxt.isoformat()))
        cur = nxt
    print(f"today {t}  window {start}..{t}  currently covered {first}..{end} gaps {gaps}")
    print(f"{'FULL 60-day' if full else 'incremental'} return pull: {len(rng)} chunk(s) of {CHUNK} days (save each as zoho_raw90/cmp_returns_<A>_<B>.json):")
    for a, b in rng:
        print(f"   {a.replace('-', '')}_{b.replace('-', '')}   created_at >= '{a}' AND created_at < '{b}'")
    print("query shape: see the docstring of build_complaints.py (ClickHouse MCP, serviceId 790ddad5-a6ff-4b03-b135-9292547ed6b6)")
    print("\nother session-only steps: damage photos (damage_images.py sheets/merge), swap + RCA pulls (CLAUDE.md checklists)\n")
    print_gates(gates())


# ------------------------------------------------------------------------------------------------ build
STEPS = [
    ("Zoho complaint tickets (incremental, last 3 days)", ["python3", "pull_complaint_tickets.py"]),
    ("complaint baseline (pass 1)", ["python3", "build_complaints.py"]),
    ("warehouse comments for new / provisional tickets", ["python3", "recheck_wh_comments.py", "--extra", "zoho_raw90/cmp_tickets_to_read.json"]),
    ("complaint baseline (pass 2, with verdicts)", ["python3", "build_complaints.py"]),
    ("views, specs, summary", ["python3", "cmp_view_spec.py"]),
    ("website", ["python3", "build_html.py"]),
    ("tests: complaints", ["python3", "test_complaints.py"]),
    ("tests: JS evaluator wfr", ["node", "test_view_js.js", "wfr"]),
    ("tests: JS evaluator damage", ["node", "test_view_js.js", "damage"]),
    ("tests: JS evaluator swap", ["node", "test_view_js.js", "swap"]),
]


def build():
    for label, cmd in STEPS:
        print(f"\n=== {label}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd, cwd=HERE)
        if r.returncode:
            print(f"\nSTOP: step failed ({label}). Fix before shipping.")
            sys.exit(r.returncode)
    print("\n=== gates")
    if not print_gates(gates()):
        sys.exit(1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        plan()
    elif cmd == "build":
        build()
    elif cmd == "gates":
        sys.exit(0 if print_gates(gates()) else 1)
    else:
        raise SystemExit(__doc__)
