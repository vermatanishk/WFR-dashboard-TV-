"""
Sanity check: can the RCA view be rebuilt from the order-level export ALONE?
Rebuilds every cell of rca_trend.json using only rca_export.json (columns -> same predicates the dashboard
rows use) and diffs it against the shipped rca_trend.json. Run: python3 pipeline/check_view_from_export.py
"""
import json
from pathlib import Path

H = Path(__file__).parent
E = json.loads((H / "rca_export.json").read_text())
T = json.loads((H / "rca_trend.json").read_text())
col = {c: i for i, c in enumerate(E["columns"])}
rows = [r for r in E["rows"] if r[col["Created date"]] <= T["t2_cutoff"]]


def g(r, name):
    return r[col[name]]


def issue(r):
    return g(r, "Issue")


P = {}
P["raised"] = lambda r: True
inv1 = lambda r: g(r, "Investigation bucket 1")
inv2 = lambda r: g(r, "Investigation bucket 2")
ret = lambda r: g(r, "Return request")
b1 = lambda r: g(r, "Raised bucket 1")
b2 = lambda r: g(r, "Raised bucket 2")
b3 = lambda r: g(r, "Raised bucket 3")
ND = ["Footage not available", "Batch not from our inventory", "CX image not clear", "Dependency not marked", "DocPharma order",
      "COGS < 100", "Agent mistake (WH marked, no WH comment)", "Return not received at WH", "Other WH note"]
NOW = lambda r: inv1(r) == "No decision"
P["WH Accepted"] = lambda r: inv1(r) == "Accepted"
P["WH Rejected"] = lambda r: inv1(r) == "Rejected"
P["No decision"] = NOW
P["Not yet read"] = lambda r: inv1(r) == "Not yet read"
for n in ND:
    P["↳ " + n] = (lambda n: lambda r: NOW(r) and inv2(r) == n)(n)
P["↳ return raised"] = lambda r: NOW(r) and ret(r) == "Raised"
P["↳ return cancelled"] = lambda r: NOW(r) and ret(r) == "Cancelled"
P["↳ return request not raised"] = lambda r: NOW(r) and ret(r) == "Not raised"

WM = lambda r: issue(r) == "Wrong medicine"
P["Wrong medicine"] = WM
P["wm_read"] = lambda r: WM(r) and b1(r) != "Photo not read yet"
P["wm_unread"] = lambda r: WM(r) and b1(r) == "Photo not read yet"
P["↳ photo shows the ordered SKU"] = lambda r: WM(r) and b1(r) in ("Photo shows the ordered SKU", "Photo shows another line of the order")
P["↳ same medicine, different pack form"] = lambda r: WM(r) and b1(r) == "Same medicine, different pack form"
P["↳ different medicine"] = lambda r: WM(r) and b1(r) == "Different medicine"
P["↳ SKU name not readable"] = lambda r: WM(r) and b1(r) == "SKU name not readable"
P["↳ bin link (picking error)"] = lambda r: WM(r) and b1(r) == "Different medicine" and b2(r) == "Bin link (picking error)"
P["↳ batch shared with ordered line"] = lambda r: WM(r) and b1(r) == "Different medicine" and b2(r) == "Batch shared with ordered line"

EX = lambda r: issue(r) == "Expiry"
P["Expiry"] = EX
P["↳ outright expired (allocation)"] = lambda r: EX(r) and b1(r) == "Outright expired"
P["↳ near expiry <3 months (allocation)"] = lambda r: EX(r) and b1(r) == "Near expiry (<3 months)"
P["↳ >=3 months in allocation"] = lambda r: EX(r) and b1(r) == ">=3 months in allocation"
P["↳ allocation not determinable"] = lambda r: EX(r) and b1(r) == "Not determinable"
P["ex_read"] = lambda r: EX(r) and b2(r) != "Photo not read yet"
P["ex_unread"] = lambda r: EX(r) and b2(r) == "Photo not read yet"
P["↳ received item already expired"] = lambda r: EX(r) and b2(r) == "Received item already expired"
P["↳ received item near expiry <3 months"] = lambda r: EX(r) and b2(r) == "Received item near expiry (<3 months)"
P["↳ received item has >=3 months"] = lambda r: EX(r) and b2(r) == "Received item has >=3 months"
P["↳ batch read, expiry not legible"] = lambda r: EX(r) and b2(r) == "Batch read, expiry not legible"
P["ex_unclear"] = lambda r: EX(r) and b2(r) == "CX image not clear"
P["memo: batch / expiry differs from allocation"] = lambda r: EX(r) and b3(r) == "Batch/expiry differs from allocation"

DM = lambda r: issue(r) == "Damaged"
P["Damaged"] = DM
P["↳ cold chain"] = lambda r: DM(r) and b1(r) == "Cold chain"
P["↳ non-cold"] = lambda r: DM(r) and b1(r) == "Non-cold"
P["dm_nc_read"] = lambda r: DM(r) and b1(r) == "Non-cold" and b2(r) != "Photo not read yet"
P["dm_nc_unread"] = lambda r: DM(r) and b1(r) == "Non-cold" and b2(r) == "Photo not read yet"
P["memo: non-cold with a logistics exception"] = lambda r: DM(r) and b1(r) == "Non-cold" and b3(r) == "Logistics exception recorded"
MQ = lambda r: issue(r) == "Missing / short quantity"
P["Missing / short quantity"] = MQ
P["↳ SKU missing"] = lambda r: MQ(r) and b1(r) == "SKU missing"
P["↳ item missing"] = lambda r: MQ(r) and b1(r) == "Item missing"
P["memo: classified from the ticket text"] = lambda r: MQ(r) and g(r, "Evidence basis") == "Ticket text"
P["memo: default to item missing"] = lambda r: MQ(r) and g(r, "Evidence basis") == "Default (no detail)"
P["Order swap"] = lambda r: issue(r) == "Order swap"
P["MRP / batch mismatch"] = lambda r: issue(r) == "MRP / batch mismatch"

# map shipped rows to predicate by label (+ occurrence order for the duplicated labels)
BUCKET_LABELS = [lab for _k, lab, _w in __import__("damaged_buckets").BUCKETS]
seen_read = {"↳ photo read": [], "↳ photo not read yet": [], "↳ CX image not clear": []}
read_keys = {"↳ photo read": ["wm_read", "ex_read", "dm_nc_read"],
             "↳ photo not read yet": ["wm_unread", "ex_unread", "dm_nc_unread"],
             "↳ CX image not clear": ["↳ CX image not clear", "ex_unclear"]}  # 1st = no-decision reason, 2nd = expiry photo

def pred_for(label, nth):
    l = label.strip()
    if l in read_keys:
        key = read_keys[l][nth]
        return P[key]
    if l == "Tickets raised":
        return P["raised"]
    for b in BUCKET_LABELS:
        if l == "↳ " + b:
            return lambda r, b=b: DM(r) and b1(r) == "Non-cold" and b2(r) == b
    if l in P:
        return P[l]
    # shipped labels that carry a different glyph for the memo / unclear rows
    return None


counts = {}
bad = missing = 0
mismatches = []
for r in T["rows"]:
    l = r["label"].strip()
    nth = counts.get(l, 0)
    counts[l] = nth + 1
    f = pred_for(r["label"], nth)
    if f is None:
        missing += 1
        mismatches.append((r["label"], "NO PREDICATE"))
        continue
    # compare every day + totals
    def n_for(days):
        s = set(days)
        return sum(1 for x in rows if x[col["Created date"]] in s and f(x))
    exp = {"3mo": T["days"], "1mo": T["days"][-30:], "2wk": T["days"][-14:]}
    for k, ds in exp.items():
        if n_for(ds) != r[k]["n"]:
            bad += 1
            mismatches.append((r["label"], k, n_for(ds), r[k]["n"]))
    for d in T["days"]:
        if n_for([d]) != r["daily"][d]["n"]:
            bad += 1
            mismatches.append((r["label"], d, n_for([d]), r["daily"][d]["n"]))
total_cells = len(T["rows"]) * (3 + len(T["days"]))
print(f"rows {len(T['rows'])}, cells {total_cells}, mismatching cells {bad}, rows without a predicate {missing}")
for m in mismatches[:25]:
    print("  ", m)
raise SystemExit(0 if (bad == 0 and missing == 0) else 1)
