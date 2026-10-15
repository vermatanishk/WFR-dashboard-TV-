"""
Independent check: rebuild every cell of rca_trend.json (All and each return state) from rca_export.json using
HAND-WRITTEN predicates (not the shared spec) and diff against the shipped view.
Run: python3 pipeline/check_view_from_export.py
"""
import json
from pathlib import Path

H = Path(__file__).parent
E = json.loads((H / "rca_export.json").read_text())
T = json.loads((H / "rca_trend.json").read_text())
C = {c: i for i, c in enumerate(E["columns"])}
UNREAD, NA = "Photo not read yet", "Photo not available (no return request)"
ND = {"Footage not available", "Batch not from our inventory", "CX image not clear", "Dependency not marked", "DocPharma order",
      "COGS < 100", "Agent mistake (WH marked, no WH comment)", "Return not received at WH", "Other WH note"}


def g(r, n):
    return r[C[n]]


i1 = lambda r: g(r, "Investigation bucket 1")
i2 = lambda r: g(r, "Investigation bucket 2")
b1 = lambda r: g(r, "Raised bucket 1")
b2 = lambda r: g(r, "Raised bucket 2")
b3 = lambda r: g(r, "Raised bucket 3")
iss = lambda r: g(r, "Issue")
nd = lambda r: i1(r) == "No decision"
wm = lambda r: iss(r) == "Wrong medicine"
ex = lambda r: iss(r) == "Expiry"
dm = lambda r: iss(r) == "Damaged"
nc = lambda r: dm(r) and b1(r) == "Non-cold"
mq = lambda r: iss(r) == "Missing / short quantity"
BK = {"dmb_primary_pack_breached": "Primary pack breached: blister punctured/burst, sachet torn, strip crushed",
      "dmb_carton_damaged": "Individual carton crushed, torn or water-soaked; product intact",
      "dmb_outer_shipper_damaged": "Courier / outer shipper crushed or torn; product inside intact",
      "dmb_leak_spill": "Liquid / gel leaked or spilled",
      "dmb_product_quality": "Product itself defective (split tablet, lumpy formula, dose delivery)",
      "dmb_label_closure_defect": "Vial label peeled off / flip-off cap loose",
      "dmb_no_visible_damage": "Photo shows the product intact - no visible damage",
      "dmb_image_not_relevant": "Image not relevant: only the app logo, or a photo of a different product"}

BIN_B = ["Bin link (picking error)", "Bin link + batch shared"]
BATCH_B = ["Batch shared with ordered line"]

P = {
    "raised": lambda r: True,
    "accepted": lambda r: i1(r) == "Accepted", "rejected": lambda r: i1(r) == "Rejected", "no_decision": nd,
    "not_yet_read": lambda r: i1(r) == "Not yet read",
    "wm": wm, "wm_read": lambda r: wm(r) and b1(r) not in (UNREAD, NA), "wm_unread": lambda r: wm(r) and b1(r) == UNREAD,
    "wm_na": lambda r: wm(r) and b1(r) == NA,
    "wm_same": lambda r: wm(r) and b1(r) in ("Photo shows the ordered SKU", "Photo shows another line of the order"),
    "wm_variant": lambda r: wm(r) and b1(r) == "Same family medicine",
    "wm_diff": lambda r: wm(r) and b1(r) == "Different medicine",
    "wm_variant_bin": lambda r: wm(r) and b1(r) == "Same family medicine" and b2(r) in BIN_B,
    "wm_variant_batch": lambda r: wm(r) and b1(r) == "Same family medicine" and b2(r) in BATCH_B,
    "wm_variant_other": lambda r: wm(r) and b1(r) == "Same family medicine" and b2(r) not in BIN_B + BATCH_B,
    "wm_diff_bin": lambda r: wm(r) and b1(r) == "Different medicine" and b2(r) in BIN_B,
    "wm_diff_batch": lambda r: wm(r) and b1(r) == "Different medicine" and b2(r) in BATCH_B,
    "wm_diff_other": lambda r: wm(r) and b1(r) == "Different medicine" and b2(r) not in BIN_B + BATCH_B,
    "wm_undet_bin": lambda r: wm(r) and b1(r) == "Not readable" and b2(r) in BIN_B,
    "wm_undet_batch": lambda r: wm(r) and b1(r) == "Not readable" and b2(r) in BATCH_B,
    "wm_undet_other": lambda r: wm(r) and b1(r) == "Not readable" and b2(r) not in BIN_B + BATCH_B,
    "wm_undet": lambda r: wm(r) and b1(r) == "Not readable",
    "ex": ex,
    "ex_alloc_out": lambda r: ex(r) and b1(r) == "Outright expired",
    "ex_alloc_near": lambda r: ex(r) and b1(r) == "Near expiry (<3 months)",
    "ex_alloc_ok": lambda r: ex(r) and b1(r) == ">=3 months in allocation",
    "ex_alloc_undet": lambda r: ex(r) and b1(r) == "Not determinable",
    "ex_read": lambda r: ex(r) and b2(r) not in (UNREAD, NA), "ex_unread": lambda r: ex(r) and b2(r) == UNREAD,
    "ex_na": lambda r: ex(r) and b2(r) == NA,
    "ex_img_expired": lambda r: ex(r) and b2(r) == "Received item already expired",
    "ex_img_near": lambda r: ex(r) and b2(r) == "Received item near expiry (<3 months)",
    "ex_img_ok": lambda r: ex(r) and b2(r) == "Received item has >=3 months",
    "ex_img_batchonly": lambda r: ex(r) and b2(r) == "Batch read, expiry not legible",
    "ex_img_unclear": lambda r: ex(r) and b2(r) == "CX image not clear",
    "ex_diff": lambda r: ex(r) and b3(r).startswith("Differs - "),
    "ex_diff_exp": lambda r: ex(r) and b3(r) == "Differs - received item expired",
    "ex_diff_notexp": lambda r: ex(r) and b3(r) == "Differs - received item not expired",
    "ex_diff_unk": lambda r: ex(r) and b3(r) == "Differs - expiry not legible",
    "dm": dm, "dm_cold": lambda r: dm(r) and b1(r) == "Cold chain", "dm_nc": nc,
    "dm_nc_read": lambda r: nc(r) and b2(r) not in (UNREAD, NA), "dm_nc_unread": lambda r: nc(r) and b2(r) == UNREAD,
    "dm_nc_na": lambda r: nc(r) and b2(r) == NA,
    "dm_nc_log": lambda r: nc(r) and b3(r) == "Logistics exception recorded",
    "mq": mq, "mq_sku": lambda r: mq(r) and b1(r) == "SKU missing", "mq_item": lambda r: mq(r) and b1(r) == "Item missing",
    "mq_text": lambda r: mq(r) and g(r, "Evidence basis") == "Ticket text",
    "mq_default": lambda r: mq(r) and g(r, "Evidence basis") == "Default (no detail)",
    "sw": lambda r: iss(r) == "Order swap", "mrp": lambda r: iss(r) == "MRP / batch mismatch",
    "not_available": None,
}
for n in ND:
    P["nd_" + n] = (lambda n: lambda r: nd(r) and i2(r) == n)(n)
for k, lab in BK.items():
    P[k] = (lambda lab: lambda r: nc(r) and b2(r) == lab)(lab)

cut = T["t2_cutoff"]
bad = miss = cells = 0
for vname, rs in (("All", None), ("Raised", "Raised"), ("Cancelled", "Cancelled"), ("Not raised", "Not raised")):
    view = T if rs is None else T["by_return"][rs]
    rows = [r for r in E["rows"] if r[C["Created date"]] <= cut and (rs is None or g(r, "Return request") == rs)]
    for tr in view["rows"]:
        f = P.get(tr["key"])
        if f is None:
            miss += 1
            print("NO PREDICATE", tr["key"])
            continue
        def n_for(ds):
            s = set(ds)
            return sum(1 for r in rows if g(r, "Created date") in s and f(r))
        for k, ds in (("3mo", T["days"]), ("1mo", T["days"][-30:]), ("2wk", T["days"][-14:])):
            cells += 1
            if n_for(ds) != tr[k]["n"]:
                bad += 1
                print("DIFF", vname, tr["key"], k, n_for(ds), tr[k]["n"])
        for d in T["days"]:
            cells += 1
            if n_for([d]) != tr["daily"][d]["n"]:
                bad += 1
print(f"cells {cells}, mismatches {bad}, rows without predicate {miss}")
raise SystemExit(0 if bad == 0 and miss == 0 else 1)
