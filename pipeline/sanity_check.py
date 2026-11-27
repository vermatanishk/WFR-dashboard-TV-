"""
Sanity check of every number the sheet / website shows, up to T-2 (owner request 2026-11-20: "sanity check run on all values up to 18 Nov").
Prints PASS / WARN / FAIL per check and writes pipeline/sanity_report.json (committed: the Info tab of the sheet shows it).

  python3 pipeline/sanity_check.py [CAP]      # CAP defaults to IST today - 2; exit 1 if any FAIL

Sections (mirrors the owner's definitions):
  1. Total cases   = UNION of ClickHouse return requests (final reason per item) and Zoho tickets of WFR dispositions
                     (independent recount lives in test_complaints.py; here: type totals reconcile across every export + tab).
  2. WH accepted   = explicit read of an admission in the Warehouse comment thread. Three independent sources must agree:
                     wh_text_check.json verdicts, the EOD history (build_eod_auto.py) and the complaint baseline rows.
  3. Order swap    = every in-scope swap complaint has a case; residual "Pair not identified" / "Unclassified" cases are reported and must have been image-checked.
  4. Order damage  = every physical-damage return image read and tagged into a bucket.
  5. Freshness     = every layer reaches the cap day; archive intact.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
res = []   # (status, section, text)


def js(name):
    return json.loads((HERE / name).read_text())


def note(status, section, text):
    res.append((status, section, text))
    print(f"{status:5} [{section}] {text}")


def ist_today():
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


def main(cap):
    ce = js("complaints_export.json")
    C = {c: i for i, c in enumerate(ce["columns"])}
    rows = [r for r in ce["rows"] if r[C["Created date"]] <= cap]
    lo = (datetime.strptime(cap, "%Y-%m-%d").date() - timedelta(days=59)).isoformat()
    win = [r for r in rows if r[C["Created date"]] >= lo]

    # ---------- 1. total cases
    by_type = Counter(r[C["Complaint type"]] for r in win)
    note("INFO", "1 total", f"window {lo}..{cap}: {len(win)} complaints (order x type) = {dict(by_type)}")
    src = Counter(r[C["Source"]] for r in win)
    note("INFO", "1 total", f"source split (return request vs ticket): {dict(src)}")
    for name, types in (("cmp_wfr_export.json", {"Wrong medicine", "Missing / short qty", "Expiry", "MRP / batch mismatch"}),
                        ("cmp_damage_export.json", {"Damage"}), ("cmp_swap_baseline_export.json", {"Order swap"})):
        e = js(name); c = e["columns"].index("Complaint type"); d = e["columns"].index("Created date")
        n = sum(1 for r in e["rows"] if lo <= r[d] <= cap)
        want = sum(v for k, v in by_type.items() if k in types)
        note("PASS" if n == want else "FAIL", "1 total", f"{name}: {n} rows in window vs {want} in complaints_export")
    # source union: nothing is dropped between the two sources
    only_t = sum(1 for r in win if r[C["Source"]] == "Zoho ticket only")
    note("INFO", "1 total", f"{only_t} complaints exist only as a Zoho ticket (no return request) and are counted")

    # ---------- 2. WH accepted
    wh = json.loads((RAW / "wh_text_check.json").read_text())
    adm = {t for t, v in wh.items() if v.get("verdict") == "admitted"}
    # complaint baseline: ticketed rows that are WH accepted
    base_rows = [r for r in win if r[C["WH input"]] == "WH accepted"]
    base_acc = {str(r[C["Ticket ID"]]) for r in base_rows if r[C["Ticket ID"]]}
    # a complaint row is accepted when ANY ticket of the case carries an admission, so the check is per order
    adm_orders = {str(v.get("order_id")) for t, v in wh.items() if v.get("verdict") == "admitted"}
    adm_orders |= {str(t["order_id"]) for t in js("data.json")["tickets"] if str(t["ticket_id"]) in adm}
    notadm = sorted(str(r[C["Order ID"]]) for r in base_rows if str(r[C["Order ID"]]) not in adm_orders)
    note("PASS" if not notadm else "FAIL", "2 WH accepted", f"{len(base_rows)} accepted complaint rows; {len(notadm)} orders without any 'admitted' ticket verdict {notadm[:5]}")
    ewrong = []
    hist = js("eod_history.json") if (HERE / "eod_history.json").exists() else {}
    eod_acc = set()
    for day, rec in hist.items():
        if lo <= day <= cap:
            for t in rec.get("accepted_tickets", []):
                tid = str(t["ticket_id"] if isinstance(t, dict) else t)
                eod_acc.add(tid)
                if tid not in adm:
                    ewrong.append(tid)
    note("PASS" if not ewrong else "FAIL", "2 WH accepted", f"EOD history: {len(eod_acc)} admissions across {sum(1 for d in hist if lo <= d <= cap)} days; {len(ewrong)} not in the verdict cache {ewrong[:5]}")
    # admitted verdicts for tickets in window that the baseline does not count (multi-order ticket / no return record / out of window)
    d_tick = {str(t["ticket_id"]): t for t in js("data.json")["tickets"]}
    win_adm = {t for t in adm if t in d_tick and lo <= d_tick[t]["created_time"][:10] <= cap}
    base_acc_orders = {str(r[C["Order ID"]]) for r in base_rows}
    missing = sorted(t for t in win_adm if str(d_tick[t]["order_id"]) not in base_acc_orders)
    note("PASS" if not missing else "WARN", "2 WH accepted", f"{len(win_adm)} admitted verdicts on dashboard tickets in window; {len(missing)} whose ORDER is not WH accepted in the baseline "
         f"(no return request yet / multi-order ticket / complaint type differs): {missing[:8]}")
    # same admitted set per macro table
    mt = js("macro_trend.json")
    row = next(r for r in mt["rows"] if r["label"] == "WH Accepted")
    tot = sum(v["accepted"] for k, v in row["daily"].items() if lo <= k <= cap)
    note("INFO", "2 WH accepted", f"macro table 'WH Accepted' (T-2 capped) sums to {tot} in the window; complaint baseline shows {len(base_acc)}; EOD {len(eod_acc)}")
    unread = [r[C["Ticket ID"]] for r in win if r[C["WH input"]] == "Verdict not read (gap)"]
    note("PASS" if not unread else "FAIL", "2 WH accepted", f"{len(unread)} tickets past T-2 with no read verdict {unread[:6]}")
    prov = [t for t, v in wh.items() if v.get("verdict") in ("no_wh_comment", "unrecognized") and t in d_tick
            and lo <= d_tick[t]["created_time"][:10] <= (datetime.strptime(cap, "%Y-%m-%d").date() - timedelta(days=0)).isoformat()
            and (v.get("rechecked_on") or "0") < (ist_today() - timedelta(days=1)).isoformat()
            and d_tick[t]["created_time"][:10] >= (ist_today() - timedelta(days=7)).isoformat()]
    note("PASS" if not prov else "FAIL", "2 WH accepted", f"{len(prov)} provisional verdicts (last 7 days) not re-read since yesterday")

    # ---------- 3. swap
    sw = js("swap_export.json")
    S = {c: i for i, c in enumerate(sw["columns"])}
    note("PASS" if sw["t2_cap_date"] >= cap else "FAIL", "3 swap", f"swap export reaches {sw['t2_cap_date']} (cap {cap})")
    cnt = Counter(r[S["Swap bucket 1"]] for r in sw["rows"])
    resid = cnt.get("Pair not identified", 0) + cnt.get("Unclassified", 0)
    seed = json.loads((RAW / "swap_pairs_seed.json").read_text())
    checked = set(seed.get("image_checked", {}).get("orders", []))
    unch = [r[0] for r in sw["rows"] if r[S["Swap bucket 1"]] in ("Pair not identified", "Unclassified") and r[S["Created date"]] <= cap and r[0] not in checked]
    note("INFO", "3 swap", f"attribution {dict(cnt)}; {resid} residual cases (no readable evidence of the other order after image check)")
    note("PASS" if not unch else "FAIL", "3 swap", f"{len(unch)} residual cases never image-checked {unch[:6]}")
    swap_c = {str(r[C["Order ID"]]) for r in win if r[C["Complaint type"]] == "Order swap" and r[C["In scope"]] == "Yes"}
    covered = {str(r[S["Order ID"]]) for r in sw["rows"]} | {str(r[S["Pair order"]]) for r in sw["rows"] if r[S["Pair order"]]}
    miss = sorted(swap_c - covered)
    note("PASS" if not miss else "FAIL", "3 swap", f"{len(swap_c) - len(miss)}/{len(swap_c)} in-scope swap complaints in the window have a case; {len(miss)} missing {miss[:6]}")

    # ---------- 4. damage
    dmg = [r for r in win if r[C["Complaint type"]] == "Damage"]
    bk = Counter(r[C["Photo bucket"]] for r in dmg)
    unread = bk.get("Photo not read yet", 0)
    note("PASS" if not unread else "FAIL", "4 damage", f"{len(dmg)} damage complaints; {unread} still 'Photo not read yet' in {lo}..{cap}")
    note("INFO", "4 damage", f"buckets: {bk.most_common()}")

    # ---------- 6. order level: one order = one count, never twice across days
    ce = js("complaints_export.json"); cc = {c: i for i, c in enumerate(ce["columns"])}
    k = Counter((r[0], r[cc["Complaint type"]]) for r in ce["rows"])
    note("PASS" if all(v == 1 for v in k.values()) else "FAIL", "6 order level", f"complaint rows: one row per (order, type): {len(ce['rows'])} rows, {sum(1 for v in k.values() if v > 1)} duplicates")
    dates = defaultdict(set)
    for r in ce["rows"]:
        dates[(r[0], r[cc["Complaint type"]])].add(r[1])
    note("PASS" if all(len(v) == 1 for v in dates.values()) else "FAIL", "6 order level", "no (order, type) complaint sits on 2 days")
    wfr = [r for r in ce["rows"] if r[cc["Complaint type"]] in ("Wrong medicine", "Missing / short qty", "Expiry", "MRP / batch mismatch") and r[1] <= cap]
    by_o = Counter(r[0] for r in wfr)
    note("INFO", "6 order level", f"WFR complaints to {cap}: {len(wfr)} rows = {len(by_o)} unique orders ({sum(1 for v in by_o.values() if v > 1)} orders carry 2+ WFR complaint types, counted once per type by design)")
    dd = js("data.json")["tickets"]
    prim = [t for t in dd if not t.get("dup_of")]
    note("PASS" if len({t["order_id"] for t in prim}) == len(prim) else "FAIL", "6 order level", f"dashboard dataset: {len(dd)} tickets -> {len(prim)} order-level rows, {len(dd) - len(prim)} repeat tickets ignored")
    mt = js("macro_trend.json")
    capt = mt["t2_cutoff"]
    want = sum(1 for t in prim if t["created_time"][:10] <= capt)
    got = next(r for r in mt["rows"] if r["label"] == "Return Requested")["3mo"]
    note("PASS" if got["raised"] == want else "FAIL", "6 order level", f"macro table 'Return Requested' raised {got['raised']} vs unique orders to {capt}: {want}")
    from collections import defaultdict as _dd
    acc = sum(1 for t in prim if t["created_time"][:10] <= capt and t["accepted"])
    adm_any = {t["order_id"] for t in dd if t["accepted"] and t["created_time"][:10] <= capt}
    note("PASS" if acc >= len({o for o in adm_any if o in {t['order_id'] for t in prim}}) - 0 and acc == len(adm_any & {t['order_id'] for t in prim if t['created_time'][:10] <= capt}) else "FAIL",
         "6 order level", f"orders accepted (any ticket admitted): {len(adm_any)} orders vs {acc} counted on representative tickets")

    # ---------- 5. freshness / archive
    for f in ("complaints_export", "cmp_wfr_export", "cmp_damage_export", "cmp_swap_baseline_export", "swap_export", "rca_export"):
        e = js(f + ".json")
        note("PASS" if e["t2_cap_date"] >= cap else "FAIL", "5 fresh", f"{f} reaches {e['t2_cap_date']}")
    note("PASS" if js("data_eod.json")["for_date"] >= cap else "FAIL", "5 fresh", f"EOD tab date {js('data_eod.json')['for_date']}")
    rc = js("rca_export.json")
    pend = Counter(x for r in rc["rows"] if r[rc["columns"].index("Created date")] <= cap for x in r if x in ("Photo not read yet", "Tags pending"))
    note("PASS" if not pend else "FAIL", "5 fresh", f"RCA columns with unfinished inputs in the window: {dict(pend) or 'none'} (photo reads / item-missing tags)")
    from archive_exports import check as archive_check
    bad = archive_check()
    note("PASS" if not bad else "FAIL", "5 fresh", "archive intact" if not bad else "; ".join(bad))

    out = {"cap": cap, "window": [lo, cap], "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "checks": [{"status": s, "section": sec, "text": t} for s, sec, t in res],
           "fail": sum(1 for s, _, _ in res if s == "FAIL"), "pass": sum(1 for s, _, _ in res if s == "PASS")}
    (HERE / "sanity_report.json").write_text(json.dumps(out, indent=1))
    print(f"\n{out['pass']} pass, {out['fail']} fail  -> pipeline/sanity_report.json")
    return out["fail"]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cap = args[0] if args else (ist_today() - timedelta(days=2)).isoformat()
    fails = main(cap)
    sys.exit(0 if "--soft" in sys.argv else (1 if fails else 0))
