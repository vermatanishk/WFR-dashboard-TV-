"""Tests for the all-complaint WFR root-cause cuts (wfr_rca.py) against complaints_export.json."""
import json
import sys
from collections import Counter
from pathlib import Path

import wfr_rca as W

HERE = Path(__file__).parent
bad = 0


def check(name, ok, extra=""):
    global bad
    print(("PASS " if ok else "FAIL ") + name + (" " + extra if extra and not ok else ""))
    bad += 0 if ok else 1


# unit rules
check("LASA: truzadon / trusadon", W.lasa_like("Truzadon 35mg", "Trusadon-35 MR"))
check("not LASA: unrelated names", not W.lasa_like("Olaptanol", "Flurisone"))
check("squash: Flexipep G == Flexi Pep-G", W.squash("Flexipep G Sachet 10.7gm") == W.squash("Flexi Pep-G"))
check("day-1 expiry = end of month", W._exp_date("2027-03-01").day == 31)
check("explicit expiry date kept", W._exp_date("2027-03-15").day == 15)

e = json.loads((HERE / "complaints_export.json").read_text())
C = {c: i for i, c in enumerate(e["columns"])}
last = max(r[1] for r in e["rows"])
from datetime import datetime, timedelta
first = (datetime.strptime(last, "%Y-%m-%d") - timedelta(days=W.WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
for typ, tree in W.TREE.items():
    rows = [r for r in e["rows"] if r[C["Complaint type"]] == typ and r[C["In scope"]] == "Yes"]
    allowed = {c1: set(c2s) | {""} for c1, c2s in tree}
    wrong = [r[0] for r in rows if r[C["WFR cut 1"]] not in allowed or r[C["WFR cut 2"]] not in allowed.get(r[C["WFR cut 1"]], set())]
    check(f"{typ}: every in-scope complaint sits in exactly one leaf of the tree", not wrong, str(wrong[:5]))
    win = [r for r in rows if r[1] >= first]
    pend = [r[0] for r in win if W.PENDING in (r[C["WFR cut 1"]], r[C["WFR cut 2"]])]
    check(f"{typ}: no 'Inputs pending' inside the 60-day window", not pend, f"{len(pend)} orders {pend[:6]}")
    old = [r for r in win if r[C["WFR cut 1"]] == W.OLD]
    check(f"{typ}: nothing in the window is marked 'older than window'", not old)
    out = [r for r in rows if r[1] < first and r[C["WFR cut 1"]] != W.OLD]
    check(f"{typ}: rows older than the window are marked as such", not out)
    # cut 2 must split cut 1 completely whenever the tree defines one
    for c1, c2s in tree:
        if c2s:
            sub = [r for r in rows if r[C["WFR cut 1"]] == c1]
            check(f"{typ}/{c1[:30]}: second cut covers all", all(r[C["WFR cut 2"]] in c2s for r in sub))
oos = [r for r in e["rows"] if r[C["In scope"]] == "No" and r[C["WFR cut 1"]]]
check("excluded (cancelled / rejected) complaints carry no cut", not oos)
print(f"\n{bad} failure(s)")
sys.exit(1 if bad else 0)
