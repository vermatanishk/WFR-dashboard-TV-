"""
Layout of the "Order Swap" tab (Google Sheet) -> swap_view_spec.json + swap_trend.json. Same declarative engine as
rca_view_spec.py (evaluated in Python here and in Apps Script by computeView_), over swap_export.json columns.

Order (owner, 2026-10-16): Total cases -> Raised funnel (return request) -> Investigation funnel -> Swap MECE (outcome).
"""
import json
from pathlib import Path

from rca_view_spec import ND, RET_STATES, _cascade, evaluate

HERE = Path(__file__).parent
I1, I2, RET, S1, S2 = "Investigation bucket 1", "Investigation bucket 2", "Return request", "Swap bucket 1", "Swap bucket 2"


def build_layout():
    L = []

    def add(key, label, sub, parent, head, where):
        L.append({"key": key, "label": label, "sub": sub, "parent": parent, "indent": 0, "head": head, "where": [list(c) for c in where]})

    add("cases", "Order swap cases", "a swap pair counts once; unpaired orders count once", None, True, [])
    # raised funnel
    add("rf_raised", "Return request raised", "of cases", "cases", False, [(RET, "in", [s for s in RET_STATES if s != "Not raised"])])
    for s in RET_STATES[:-1]:
        add("rf_" + s, s.replace("Raised - ", ""), "of return raised", "rf_raised", False, [(RET, "in", [s])])
    add("rf_not", "Return request not raised", "of cases", "cases", False, [(RET, "in", ["Not raised"])])
    # investigation funnel
    add("accepted", "WH Accepted", "investigation, of cases", "cases", False, [(I1, "in", ["Accepted"])])
    add("rejected", "WH Rejected", "of cases", "cases", False, [(I1, "in", ["Rejected"])])
    nd = [(I1, "in", ["No decision"])]
    add("no_decision", "No decision", "of cases", "cases", False, nd)
    for n in ND:
        add("nd_" + n, n, "of no decision", "no_decision", False, nd + [(I2, "in", [n])])
    add("not_yet_read", "Not yet read", "held back inside T-2 or no WH verdict cached", "cases", False, [(I1, "in", ["Not yet read"])])
    # MECE outcome
    wh = [(S1, "in", ["WH issue"])]
    add("wh", "WH issue", "same warehouse, warehouse-side link, different pincodes", "cases", True, wh)
    add("wh_pack", "Proximity in packing, separate manifestation", "same handler at invoice / carrier-pickup <= 10 min, manifests far apart", "wh", False, wh + [(S2, "in", ["Proximity in packing, separate manifestation"])])
    add("wh_man", "Manifested too closely", "same handler manifested both parcels <= 60 s apart", "wh", False, wh + [(S2, "in", ["Manifested too closely"])])
    add("wh_oth", "Other", "shared handler at some stage, not close in time", "wh", False, wh + [(S2, "in", ["Other"])])
    lg = [(S1, "in", ["Logistics issue"])]
    add("lg", "Logistics issue", "same pincode, or error not attributable to the warehouse", "cases", True, lg)
    add("lg_pin", "Same pincode delivery", "", "lg", False, lg + [(S2, "in", ["Same pincode delivery"])])
    add("lg_day", "Same day diff pincode delivery", "no warehouse link, both delivered the same day", "lg", False, lg + [(S2, "in", ["Same day diff pincode delivery"])])
    add("unc", "Unclassified", "pair found, but no warehouse link and not same-day delivery", "cases", True, [(S1, "in", ["Unclassified"])])
    add("pni", "Pair not identified", "ticket names no second order - cannot be classified", "cases", True, [(S1, "in", ["Pair not identified"])])
    return _cascade(L)


def main():
    exp = json.loads((HERE / "swap_export.json").read_text())
    layout = build_layout()
    trend = evaluate(exp, layout)
    trend["by_return"] = {s: evaluate(exp, layout, s, days=trend["days"]) for s in RET_STATES}
    (HERE / "swap_trend.json").write_text(json.dumps(trend))
    (HERE / "swap_view_spec.json").write_text(json.dumps({"layout": layout, "return_states": RET_STATES, "t2_cap_date": exp["t2_cap_date"], "generated_at": exp["generated_at"]}, ensure_ascii=False, separators=(",", ":")))
    for r in trend["rows"]:
        print(("  " * r["indent"]) + r["label"], "|", r["3mo"]["text"])
    # MECE checks (3mo, All)
    n = {r["key"]: r["3mo"]["n"] for r in trend["rows"]}
    assert n["wh"] == n["wh_pack"] + n["wh_man"] + n["wh_oth"] and n["lg"] == n["lg_pin"] + n["lg_day"]
    assert n["cases"] == n["wh"] + n["lg"] + n["unc"] + n["pni"] == n["accepted"] + n["rejected"] + n["no_decision"] + n["not_yet_read"]
    assert n["cases"] == n["rf_raised"] + n["rf_not"]
    print("MECE checks OK; held back:", trend["excluded_tickets"])


if __name__ == "__main__":
    main()
