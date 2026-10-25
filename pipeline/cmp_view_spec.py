"""
Layouts of the complaint tabs (owner, 2026-10-25) -> cmp_wfr_trend.json / cmp_damage_trend.json + *_view_spec.json + cmp_summary.json.
Same declarative engine as rca_view_spec.py (evaluated here in Python and in Apps Script by computeView_), over
complaints_export.json (one row per complaint = order x complaint type; union of ClickHouse return requests and Zoho tickets).

  Tab "WFR funnel"   Wrong medicine / Missing qty / Expiry / MRP-batch complaints (Damage and Swap have their own tabs)
  Tab "Order damage" Damage complaints, incl. the photo read of what the complaint was actually about
  Tab "Order Swap"   unchanged (swap_view_spec.py)
  Tab "Summary"      <= 8 rows x 3 columns (WFR | Damage | Swap), macro numbers only (cmp_summary.json)

Counting rule: a complaint is (order, complaint type); an order with a wrong-medicine item and a damaged item is two complaints.
Return request column keeps the RCA taxonomy (Raised - Accepted & refunded / Cancelled / Rejected / In progress, Not raised) so
the same global "Return request" selector works. Rows inside the Warehouse T-2 window are shown as "Not due yet (T-2)", never as
"No WH comment" (WH needs ~2 days to comment).
"""
import json
from pathlib import Path

from build_complaints import (COLUMNS, DMG, DMG_PHYS, DMG_TEMP, EXP, MQ, MRP, P_NA, P_NOFILE, P_TEMP, P_UNREAD, R_ACC, R_CAN, R_NONE,
                              R_REJ, SRC_BOTH, SRC_RET, SRC_TKT, T_MATCH, T_NONCMP, T_NONE, T_OTHER, TYPES, WFR_TYPES, WH_ACC,
                              WH_DEN, WH_DUE, WH_GAP, WH_NONE, WH_OTH, WM)
from damaged_buckets import BUCKETS
from rca_view_spec import RET_STATES, _cascade, evaluate

HERE = Path(__file__).parent
TYPE, SRC, RET, SCOPE, REL, RAISED, WH, DT, PB = ("Complaint type", "Source", "Return request", "In scope", "Ticket relation",
                                                   "Ticket raised", "WH input", "Damage type", "Photo bucket")
LABELS = [b[1] for b in BUCKETS]
VISIBLE = LABELS[:6]            # photo shows real damage (primary pack, carton, outer shipper, leak, product quality, label/closure)


def _common(L, add, types, root_label):
    """Baseline -> exclusions -> in scope -> ticket hygiene -> Warehouse input. `types` scopes every row."""
    T = [(TYPE, "in", types)]
    add("all", root_label, "complaints in the window", None, True, T)
    add("src_both", SRC_BOTH, "customer raised it AND an investigation ticket exists", "all", False, T + [(SRC, "in", [SRC_BOTH])])
    add("src_ret", SRC_RET, "return request only: no complaint ticket", "all", False, T + [(SRC, "in", [SRC_RET])])
    add("src_tkt", SRC_TKT, "agent ticket, no return request", "all", False, T + [(SRC, "in", [SRC_TKT])])
    add("ex_can", "Return cancelled by customer", "excluded from the funnel below", "all", False, T + [(RET, "in", [R_CAN])])
    add("ex_rej", "Return rejected at QC", "excluded from the funnel below", "all", False, T + [(RET, "in", [R_REJ])])
    S = T + [(SCOPE, "in", ["Yes"])]
    add("scope", "In scope", "of complaints: not cancelled / rejected", "all", True, S)
    add("t_yes", "Zoho ticket raised (investigation ticket)", "of in scope", "scope", False, S + [(RAISED, "in", ["Yes"])])
    add("t_match", "Filed under this complaint type", "of in scope", "t_yes", False, S + [(REL, "in", [T_MATCH])])
    add("t_other", "Filed under another complaint type", "agent chose a different sub-disposition", "t_yes", False, S + [(REL, "in", [T_OTHER])])
    add("t_non", "Ticket exists but filed as non-complaint", "e.g. 'No longer needed' / pickup delayed: nobody investigates", "scope", False, S + [(REL, "in", [T_NONCMP])])
    add("t_none", "No ticket at all", "of in scope", "scope", False, S + [(REL, "in", [T_NONE])])
    return S


def _wh(add, S, parent="t_yes"):
    Y = S + [(RAISED, "in", ["Yes"])]
    add("wh_acc", "WH accepted (admitted fault)", "of ticketed", parent, False, Y + [(WH, "in", [WH_ACC])])
    add("wh_den", "WH denied", "of ticketed: stock-denial / proper-medicine reply", parent, False, Y + [(WH, "in", [WH_DEN])])
    add("wh_oth", "WH other note", "of ticketed: footage not found, duplicate, etc.", parent, False, Y + [(WH, "in", [WH_OTH])])
    add("wh_none", "No WH comment", "of ticketed, past T-2: Warehouse was never asked / never replied", parent, False, Y + [(WH, "in", [WH_NONE])])
    add("wh_due", "Not due yet (T-2)", "of ticketed: raised in the last 2 days", parent, False, Y + [(WH, "in", [WH_DUE])])
    add("wh_gap", "Verdict not read (gap)", "of ticketed: comments not read yet - must be 0", parent, False, Y + [(WH, "in", [WH_GAP])])


def wfr_layout():
    L = []

    def add(key, label, sub, parent, head, where):
        L.append({"key": key, "label": label, "sub": sub, "parent": parent, "indent": 0, "head": head, "where": [list(c) for c in where]})

    S = _common(L, add, WFR_TYPES, "Complaints (return requests + Zoho tickets)")
    _wh(add, S)
    # by complaint type: where do tickets go missing
    for t in WFR_TYPES:
        k = "ty_" + t
        add(k, t, "in-scope complaints", "scope", True, [(TYPE, "in", [t]), (SCOPE, "in", ["Yes"])])
        add(k + "_y", "Zoho ticket raised", "of " + t, k, False, [(TYPE, "in", [t]), (SCOPE, "in", ["Yes"]), (RAISED, "in", ["Yes"])])
        add(k + "_n", "No investigation ticket", "of " + t, k, False, [(TYPE, "in", [t]), (SCOPE, "in", ["Yes"]), (RAISED, "in", ["No"])])
        add(k + "_nr", "Already refunded without any ticket", "of " + t + " with no ticket", k + "_n", False,
            [(TYPE, "in", [t]), (SCOPE, "in", ["Yes"]), (RAISED, "in", ["No"]), (RET, "in", [R_ACC])])
    return _cascade(L)


def damage_layout():
    L = []

    def add(key, label, sub, parent, head, where):
        L.append({"key": key, "label": label, "sub": sub, "parent": parent, "indent": 0, "head": head, "where": [list(c) for c in where]})

    S = _common(L, add, [DMG], "Damage complaints (return requests + Zoho tickets)")
    _wh(add, S)
    for k, v, sub in (("temp", DMG_TEMP, "customer says the cold item arrived warm - not photo-read"),
                      ("phys", DMG_PHYS, "pack / product physically damaged (incl. cold items)")):
        add(k, v, "of in scope", "scope", True, S + [(DT, "in", [v])])
        add(k + "_y", "Zoho ticket raised", "of " + v.lower(), k, False, S + [(DT, "in", [v]), (RAISED, "in", ["Yes"])])
        add(k + "_n", "No investigation ticket", "of " + v.lower(), k, False, S + [(DT, "in", [v]), (RAISED, "in", ["No"])])
    P = S + [(DT, "in", [DMG_PHYS])]
    add("ph_read", "Photo read", "physical damage with a complaint photo that has been read", "phys", False, P + [(PB, "in", LABELS)])
    for i, lab in enumerate(LABELS):
        k = "pb%d" % i
        add(k, lab.split(":")[0].split(" - ")[0][:80], "of photos read", "ph_read", False, P + [(PB, "in", [lab])])
        add(k + "_y", "Zoho ticket raised", "", k, False, P + [(PB, "in", [lab]), (RAISED, "in", ["Yes"])])
        add(k + "_n", "No investigation ticket", "", k, False, P + [(PB, "in", [lab]), (RAISED, "in", ["No"])])
    add("ph_vis", "Visible damage in photo (pack / carton / shipper / leak / quality / closure)", "of photos read", "ph_read", True, P + [(PB, "in", VISIBLE)])
    add("ph_vis_y", "Zoho ticket raised", "", "ph_vis", False, P + [(PB, "in", VISIBLE), (RAISED, "in", ["Yes"])])
    add("ph_vis_n", "No investigation ticket", "real damage nobody investigated", "ph_vis", False, P + [(PB, "in", VISIBLE), (RAISED, "in", ["No"])])
    add("ph_unread", P_UNREAD, "return raised, photo still to be read - must be 0 for a final view", "phys", False, P + [(PB, "in", [P_UNREAD])])
    add("ph_nofile", P_NOFILE, "return raised but no photo uploaded", "phys", False, P + [(PB, "in", [P_NOFILE])])
    add("ph_na", P_NA, "no return request, so no complaint photo exists", "phys", False, P + [(PB, "in", [P_NA])])
    return _cascade(L)


def build():
    out = {}
    for name, layout in (("wfr", wfr_layout()), ("damage", damage_layout())):
        exp = json.loads((HERE / f"cmp_{name}_export.json").read_text())
        trend = evaluate(exp, layout)
        trend["by_return"] = {s: evaluate(exp, layout, s, days=trend["days"]) for s in RET_STATES}
        (HERE / f"cmp_{name}_trend.json").write_text(json.dumps(trend))
        (HERE / f"cmp_{name}_view_spec.json").write_text(json.dumps(
            {"layout": layout, "return_states": RET_STATES, "t2_cap_date": exp["t2_cap_date"], "generated_at": exp["generated_at"]},
            ensure_ascii=False, separators=(",", ":")))
        out[name] = trend
    return out


SUMMARY_DAYS = 30


def summary():
    """Tab "Summary": at most 8 rows x 3 columns (WFR funnel | Order damage | Order swap), macro numbers only, last 30 days."""
    cols = [("WFR funnel", "cmp_wfr_export.json"), ("Order damage", "cmp_damage_export.json"), ("Order swap", "cmp_swap_baseline_export.json")]
    data = []
    for name, f in cols:
        exp = json.loads((HERE / f).read_text())
        C = {c: i for i, c in enumerate(exp["columns"])}
        last = exp["t2_cap_date"]
        from datetime import date, timedelta
        first = (date.fromisoformat(last) - timedelta(days=SUMMARY_DAYS - 1)).isoformat()
        rows = [r for r in exp["rows"] if first <= r[C["Created date"]] <= last]
        sc = [r for r in rows if r[C["In scope"]] == "Yes"]
        tk = [r for r in sc if r[C["Ticket raised"]] == "Yes"]
        wh = [r for r in tk if r[C["WH input"]] in (WH_ACC, WH_DEN, WH_OTH)]
        due = [r for r in tk if r[C["WH input"]] != WH_DUE]
        data.append(dict(name=name, first=first, last=last, n=len(rows), excl=len(rows) - len(sc), scope=len(sc), tk=len(tk), notk=len(sc) - len(tk),
                         wh=len(wh), due=len(due), acc=sum(1 for r in tk if r[C["WH input"]] == WH_ACC),
                         refunded_no_tk=sum(1 for r in sc if r[C["Ticket raised"]] == "No" and r[C["Return request"]] == R_ACC)))
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else "–"
    spec = [("Complaints raised", "return requests + Zoho tickets, last 30 days", lambda d: str(d["n"])),
            ("Cancelled / rejected by us", "excluded below", lambda d: f'{d["excl"]} | {pct(d["excl"], d["n"])}'),
            ("In scope", "of complaints", lambda d: f'{d["scope"]} | {pct(d["scope"], d["n"])}'),
            ("Zoho ticket raised", "of in scope", lambda d: f'{d["tk"]} | {pct(d["tk"], d["scope"])}'),
            ("No investigation ticket", "of in scope", lambda d: f'{d["notk"]} | {pct(d["notk"], d["scope"])}'),
            ("Warehouse input received", "of ticketed, past T-2", lambda d: f'{d["wh"]} | {pct(d["wh"], d["due"])}'),
            ("Warehouse accepted fault", "of ticketed, past T-2", lambda d: f'{d["acc"]} | {pct(d["acc"], d["due"])}'),
            ("Refunded with no ticket", "of in scope: money returned, nobody investigated", lambda d: f'{d["refunded_no_tk"]} | {pct(d["refunded_no_tk"], d["scope"])}')]
    out = {"columns": [c for c, _ in cols], "window": [data[0]["first"], data[0]["last"]],
           "rows": [{"label": l, "sub": sub, "values": [f(d) for d in data]} for l, sub, f in spec], "raw": data}
    notes = json.loads((HERE / "complaints_export.json").read_text())["notes"]
    sw = json.loads((HERE / "swap_export.json").read_text())
    out["footnotes"] = [
        f"{notes.get('unlinked_complaint_tickets', 0)} complaint-type Zoho tickets have no usable Order ID (missing / placeholder / several orders) and cannot be joined to a return request - they are NOT in these numbers (ticket hygiene gap).",
        f"Order swap column = return reason 'Order swap' / swap sub-disposition. The Order swap tab counts {len(sw['rows'])} cases found by a ticket-text scan (pairs counted once), so its totals differ.",
        "Warehouse input columns use tickets past T-2 only (the Warehouse needs ~2 days to comment). Cold-chain damage complaints are not photo-read."]
    assert len(out["rows"]) <= 8 and len(out["columns"]) == 3
    (HERE / "cmp_summary.json").write_text(json.dumps(out, ensure_ascii=False))
    return out


def main():
    out = build()
    sm = summary()
    for name, t in out.items():
        print("\n=====", name, "window", t["days"][0], "..", t["days"][-1])
        for r in t["rows"]:
            print(("  " * r["indent"]) + r["label"][:70].ljust(72 - 2 * r["indent"]), r["3mo"]["text"].rjust(11), r["1mo"]["text"].rjust(11), r["2wk"]["text"].rjust(11))
    print("\n===== summary", sm["window"])
    for r in sm["rows"]:
        print(r["label"].ljust(30), *[v.rjust(12) for v in r["values"]])


if __name__ == "__main__":
    main()
