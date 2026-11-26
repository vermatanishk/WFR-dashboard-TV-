"""
ONE entry point for the daily 7 pm refresh of EVERYTHING (owner, 2026-11-06: the refresh must not stop at the old tabs).

  python3 pipeline/refresh_all.py plan     what to pull from ClickHouse today (incremental ranges) + which gates are red
  python3 pipeline/refresh_all.py build    run every deterministic step in order (Zoho REST + builds + tests) and stop on the first failure
  python3 pipeline/refresh_all.py pending  the incremental SESSION work lists (RCA photos / item-missing tags / damage photos / swap residual image check)
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
from collections import Counter
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
    # WH verdict coverage of the core dataset (2026-11-11: unattended runs without Zoho REST creds left every new ticket uncached ->
    # considered_bod -> WH accepted showed 0 for days). Tickets older than T-2 must have a read verdict; provisional ones must be re-read.
    wh = js("zoho_raw90/wh_text_check.json")
    cap = (t - timedelta(days=2)).isoformat()
    unread = [x["ticket_id"] for x in d["tickets"] if x["created_time"][:10] <= cap and x["ticket_id"] not in wh]
    chk("core WH verdicts read (tickets past T-2)", not unread, f"{len(unread)} tickets past T-2 with no cached verdict")
    recent = {x["ticket_id"] for x in d["tickets"] if x["created_time"][:10] >= (t - timedelta(days=7)).isoformat()}
    stale_prov = [k for k in recent if (wh.get(k) or {}).get("verdict") in ("no_wh_comment", "unrecognized")
                  and (wh[k].get("rechecked_on") or "0") < (t - timedelta(days=1)).isoformat()]
    chk("core provisional verdicts re-read (last 7 days)", not stale_prov, f"{len(stale_prov)} provisional verdicts not re-read since yesterday")
    eod = js("data_eod.json")
    chk("EOD tab date = T-2", eod["for_date"] >= cap, f"for_date {eod['for_date']} (want {cap}); run build_eod_auto.py")
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
                 and r[e["columns"].index("Created date")] >= (t - timedelta(days=60)).isoformat())
    chk("damage photos read (last 60 days)", unread == 0, f"{unread} complaint rows still 'Photo not read yet'")
    # WFR root-cause cuts (owner 2026-11-27): every in-scope wrong-medicine / missing-qty / expiry complaint of the 60-day window analysed
    ci_ = e["columns"]
    pend_w = sorted({r[0] for r in e["rows"] if r[ci_.index("Created date")] >= (t - timedelta(days=61)).isoformat() and "Inputs pending" in (r[ci_.index("WFR cut 1")], r[ci_.index("WFR cut 2")])})
    chk("WFR root-cause inputs complete (60 days)", not pend_w, f"{len(pend_w)} complaints 'Inputs pending' {pend_w[:6]} - run `refresh_all.py pending` (item 5)")
    # swap + rca feeds
    sw = js("swap_export.json")
    chk("order swap export", sw["t2_cap_date"] >= (t - timedelta(days=4)).isoformat(), f"through {sw['t2_cap_date']}")
    rc = js("rca_export.json")
    chk("RCA export (root-cause columns)", rc["t2_cap_date"] >= (t - timedelta(days=4)).isoformat(), f"through {rc['t2_cap_date']}")
    rcols = rc["columns"]; rcap = (t - timedelta(days=2)).isoformat()
    rp = Counter(x for row in rc["rows"] if row[rcols.index("Created date")] <= rcap for x in row if x in ("Photo not read yet", "Tags pending"))
    chk("RCA photos read (T-2 window)", not rp.get("Photo not read yet"), f"{rp.get('Photo not read yet', 0)} orders 'Photo not read yet' - run `refresh_all.py pending`")
    chk("RCA item-missing tags (T-2 window)", not rp.get("Tags pending"), f"{rp.get('Tags pending', 0)} orders 'Tags pending' - run `refresh_all.py pending`")
    # swap (owner 2026-11-22): (1) every in-scope swap complaint of the window is covered by a case; (2) every case the evidence can attribute is attributed
    # Warehouse vs Logistics; the residue ("Pair not identified" / "Unclassified") is a reported bucket, but only once image evidence was TRIED for it
    # (swap_pairs_seed.json image_checked) - a new unpaired case therefore turns the gate red until the session has read its photos.
    sc = sw["columns"]
    seed = json.loads((RAW / "swap_pairs_seed.json").read_text())
    checked = set(seed.get("image_checked", {}).get("orders", []))
    un = [r for r in sw["rows"] if r[sc.index("Swap bucket 1")] in ("Pair not identified", "Unclassified")
          and r[sc.index("Created date")] <= cap and r[0] not in checked]
    chk("swap residual cases image-checked", not un, f"{len(un)} unpaired / unclassified swap cases not yet image-checked {[r[0] for r in un][:6]} "
        "(fetch_swap_images.py / damage_images.py sheets, read invoice + label order ids, add pairs to swap_pairs_seed.json, else add order to image_checked)")
    cov = {str(r[0]) for r in sw["rows"]} | {str(r[sc.index("Pair order")]) for r in sw["rows"] if r[sc.index("Pair order")]}
    ec = js("complaints_export.json"); ci = {c: i for i, c in enumerate(ec["columns"])}
    miss = sorted({str(x[ci["Order ID"]]) for x in ec["rows"] if x[ci["Complaint type"]] == "Order swap" and x[ci["In scope"]] == "Yes"
                   and (t - timedelta(days=60)).isoformat() <= x[ci["Created date"]] <= cap and str(x[ci["Order ID"]]) not in cov})
    chk("swap complaints all covered by a case", not miss, f"{len(miss)} in-scope swap complaints without a case {miss[:6]}")
    # archive: nothing ever leaves the git history of rows (owner 2026-11-20)
    try:
        from archive_exports import check as _archive_check
        bad = _archive_check()
        chk("archive intact (old rows kept)", not bad, "; ".join(bad))
    except Exception as ex:
        chk("archive intact (old rows kept)", False, str(ex))
    # Zoho Desk access: a creds-less / revoked run must go red instead of shipping zeros
    try:
        from zoho_auth import desk_get
        desk_get("/tickets", {"limit": 1})
        chk("Zoho Desk access", True, "ok")
    except Exception as ex:
        chk("Zoho Desk access", False, str(ex)[:120] + " - ticket pulls / WH-comment reads cannot run")
    sr = HERE / "sanity_report.json"
    if sr.exists():
        rep = json.loads(sr.read_text())
        chk("sanity_check.py (all values vs T-2)", rep["fail"] == 0 and rep["cap"] >= cap, f"{rep['fail']} failing checks, cap {rep['cap']}")
    else:
        chk("sanity_check.py (all values vs T-2)", False, "never run")
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
    print("\nsession-only incremental steps (photo reads, RCA tags, swap pairs): run `python3 pipeline/refresh_all.py pending` after the pulls\n")
    print_gates(gates())


# ------------------------------------------------------------------------------------------------ pending
def pending():
    """The incremental SESSION steps (photo reads, tags, swap pairs), as explicit work lists. Run after the REST/ClickHouse core steps and `build`
    (owner 2026-11-22: these are part of the daily routine, never skipped). Writes the order lists under zoho_raw90/ and prints the recipe."""
    t = today()
    cap = (t - timedelta(days=2)).isoformat()
    rc = js("rca_export.json"); c = rc["columns"]
    by = {"Photo not read yet": [], "Tags pending": []}
    for row in rc["rows"]:
        if row[c.index("Created date")] <= cap:
            for k in by:
                if k in row:
                    by[k].append(row[0])
    ph, tg = sorted(set(by["Photo not read yet"])), sorted(set(by["Tags pending"]))
    (RAW / "rca_photo_pending_orders.json").write_text(json.dumps(ph))
    (RAW / "rca_tags_pending_orders.json").write_text(json.dumps(tg))
    e = js("complaints_export.json"); ec = e["columns"]
    dm = sorted({r[0] for r in e["rows"] if r[ec.index("Photo bucket")] == "Photo not read yet" and r[ec.index("Created date")] >= (t - timedelta(days=60)).isoformat()})
    (RAW / "damage_pending_orders.json").write_text(json.dumps(dm))
    sw = js("swap_export.json"); sc = sw["columns"]
    seed = json.loads((RAW / "swap_pairs_seed.json").read_text())
    chk = set(seed.get("image_checked", {}).get("orders", []))
    un = sorted({r[0] for r in sw["rows"] if r[sc.index("Swap bucket 1")] in ("Pair not identified", "Unclassified") and r[sc.index("Created date")] <= cap and r[0] not in chk})
    (RAW / "swap_unpaired_orders.json").write_text(json.dumps(un))
    ci = e["columns"]
    wp = {}
    for r in e["rows"]:
        if "Inputs pending" in (r[ci.index("WFR cut 1")], r[ci.index("WFR cut 2")]):
            wp.setdefault(r[ci.index("Complaint type")], []).append((r[0], r[ci.index("WFR cut detail")]))
    (RAW / "wfr_rca_pending.json").write_text(json.dumps(wp))
    print(f"T-2 cap {cap}")
    print(f"1. RCA photos not read: {len(ph)} orders -> zoho_raw90/rca_photo_pending_orders.json   (rca_images.py, READ every sheet, merge_reads.py; CLAUDE.md photo recipe)")
    print(f"2. RCA item-missing tags pending: {len(tg)} orders -> zoho_raw90/rca_tags_pending_orders.json")
    print("     pull return lines (ClickHouse; columns quantity, order_quantity, missing_quantity, final_approved_number; reason != 'RTO'), map SKUs with the pack workbook")
    print("     (~/Downloads 'Pack Quantity & Base Value Changes*.xlsx - Sheet1.csv', header row 7), GRN signature rows (mdm_grn_po_deltas grn_qty = pack x open_po_qty);")
    print("     UNION new rows into rca_item_missing_orders / _sku / _inward_sig.json (never overwrite), then build_item_missing_tags.py -> build_rca_export.py -> build_rca_trend.py")
    print(f"3. Damage photos not read: {len(dm)} orders -> zoho_raw90/damage_pending_orders.json   (damage_images.py sheets/merge)")
    print(f"4. Swap residual cases not image-checked: {len(un)} orders -> zoho_raw90/swap_unpaired_orders.json")
    print("     ClickHouse return-item image_urls (save_ch_result.py -> swap_unpaired_images_raw.json), `damage_images.py sheets swap_sheets swap_unpaired_images_raw.json swap_unpaired_orders.json`,")
    print("     read every sheet, CROP + enlarge each invoice / courier label to read its Order ID; a different id = pair -> swap_pairs_seed.json image_pairs.pairs;")
    print("     pull swap_orders / swap_status_raw / swap_return_status for the partner orders; then add every order you tried to image_checked.orders; build_swap.py, swap_view_spec.py")
    print("     (orders with no return request: fetch_swap_images.py <ticketNumber> pulls the Zoho ticket attachments)")
    n5 = sum(len(v) for v in wp.values())
    print(f"5. WFR root-cause inputs pending: {n5} complaints -> zoho_raw90/wfr_rca_pending.json  (by type; detail says what is missing)")
    print("     pull the inputs named in wfr_rca.py's docstring / WFR_RCA_inputs.md (ClickHouse MCP, repeat('x',N) pad + save_ch_result.py), UNION into the wfr_*.json files, append the orders to")
    print("     zoho_raw90/wfr_inputs_done.json (wm / mq / exp / wm_brands), read new complaint photos (rca_images.py + merge_reads.py), run scan_pack_text.py, then build_complaints.py + cmp_view_spec.py")


# ------------------------------------------------------------------------------------------------ build
STEPS = [
    ("Zoho complaint tickets (incremental, last 3 days)", ["python3", "pull_complaint_tickets.py"]),
    ("RCA: Zoho Dependency field (incremental)", ["python3", "pull_dependency.py"]),
    ("RCA: provisional WH verdicts re-read", ["python3", "recheck_wh_comments.py"]),
    ("RCA: ticket routing history", ["python3", "pull_ticket_routing.py"]),
    ("RCA: wrong-medicine layer", ["python3", "build_rca_wrongmed.py"]),
    ("RCA: expiry inputs", ["python3", "build_rca_inputs.py"]),
    ("RCA: damaged / missing / swap extra branches", ["python3", "build_rca_extra.py"]),
    ("RCA: funnel", ["python3", "build_rca.py"]),
    ("RCA: item-missing tags", ["python3", "build_item_missing_tags.py"]),
    ("RCA: export (order-level rows)", ["python3", "build_rca_export.py"]),
    ("RCA: trend", ["python3", "build_rca_trend.py"]),
    ("swap: ticket scan (never drops old tickets)", ["python3", "pull_swap_tickets.py"]),
    ("swap: ticket routing", ["python3", "pull_swap_routing.py"]),
    ("swap: warehouse verdicts of the swap tickets", ["python3", "read_swap_wh.py"]),
    ("swap: cases", ["python3", "build_swap.py"]),
    ("swap: view spec", ["python3", "swap_view_spec.py"]),
    ("WFR root cause: pack-pattern ticket scan (incremental)", ["python3", "scan_pack_text.py", "10"]),
    ("complaint baseline (pass 1)", ["python3", "build_complaints.py"]),
    ("warehouse comments for new / provisional tickets", ["python3", "recheck_wh_comments.py", "--extra", "zoho_raw90/cmp_tickets_to_read.json"]),
    ("complaint baseline (pass 2, with verdicts)", ["python3", "build_complaints.py"]),
    ("views, specs, summary", ["python3", "cmp_view_spec.py"]),
    ("archive (append-only, old rows never dropped)", ["python3", "archive_exports.py"]),
    ("sanity check vs T-2 (informational; gates make it binding)", ["python3", "sanity_check.py", "--soft"]),
    ("website", ["python3", "build_html.py"]),
    ("tests: complaints", ["python3", "test_complaints.py"]),
    ("tests: WFR root cause", ["python3", "test_wfr_rca.py"]),
    ("tests: JS evaluator wfr", ["node", "test_view_js.js", "wfr"]),
    ("tests: JS evaluator damage", ["node", "test_view_js.js", "damage"]),
    ("tests: JS evaluator swap", ["node", "test_view_js.js", "swap"]),
    ("tests: Google-Sheet upsert never deletes rows", ["node", "test_gsheet_upsert.js"]),
    ("tests: warehouse-comment classifier", ["python3", "test_wh_comment_classifier.py"]),
    ("tests: RCA", ["python3", "test_rca.py"]),
    ("tests: RCA trend", ["python3", "test_rca_trend.py"]),
    ("tests: RCA view vs export", ["python3", "check_view_from_export.py"]),
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
    elif cmd == "pending":
        pending()
    elif cmd == "build":
        build()
    elif cmd == "gates":
        sys.exit(0 if print_gates(gates()) else 1)
    else:
        raise SystemExit(__doc__)
