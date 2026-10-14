"""
Order / ticket level export of the trailing-90-day RCA -> pipeline/rca_export.json.

Feeds the live Google Sheet (pipeline/gsheet/Code.gs): tab "Raw data" is one row per ORDER (unique per
order, first ticket wins - the same rule as the dashboard tile and the RCA view), tab "RCA view" is built
from pipeline/rca_trend.json. Both JSONs are committed to git and read by Apps Script from the raw GitHub
URL, so a refresh push updates the sheet.

No personal data: order id, ticket id, dates, warehouse, SKU / product names, buckets only. Never a person's
name, phone, address or the WH comment text.

Column groups
  keys        Order ID, Ticket ID, Created date, Warehouse, Issue (category)
  Investigation bucket 1  Accepted / Rejected / No decision / Not yet read
  Investigation bucket 2  deep dive of No decision (reason) + return request state + Zoho dependency
  Raised bucket 1/2/3     the issue tree, per category (see _raised())
  Evidence                what the call is based on and how sure it is
"""
import json
from pathlib import Path

from damaged_buckets import BUCKETS, bucket

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"

COLUMNS = [
    "Order ID", "Ticket ID", "Created date", "Warehouse", "Issue",
    "Investigation bucket 1", "Investigation bucket 2", "Return request", "Dependency (Zoho)",
    "Raised bucket 1", "Raised bucket 2", "Raised bucket 3",
    "Evidence basis", "Confidence", "Photos read", "In T-2 scope",
]
DECISION = {"accepted": "Accepted", "rejected": "Rejected", "no_decision": "No decision", "not_yet_read": "Not yet read"}
ND = {"footage_missing": "Footage not available", "batch_not_in_inventory": "Batch not from our inventory",
      "cx_image_unclear": "CX image not clear", "dependency_not_marked": "Dependency not marked",
      "docpharma": "DocPharma order", "cogs_lt_100": "COGS < 100", "agent_mistake": "Agent mistake (WH marked, no WH comment)",
      "return_not_received_at_wh": "Return not received at WH", "other_wh_note": "Other WH note"}
RET = {"raised": "Raised", "cancelled": "Cancelled", "not_raised": "Not raised"}
CAT = {"Missing/Wrong Qty": "Missing / short quantity", "Wrong Medicines": "Wrong medicine", "Expiry Issue": "Expiry",
       "Damaged/Defective": "Damaged", "Switch Orders": "Order swap", "MRP/Batch Mismatch": "MRP / batch mismatch"}
BUCKET_LABEL = {k: lab for k, lab, _ in BUCKETS}
WM = {"same_sku_consistent": "Photo shows the ordered SKU", "other_order_line_photographed": "Photo shows another line of the order",
      "same_brand_variant": "Same medicine, different pack form", "same_product_diff_packaging": "Same medicine, different pack form",
      "different_medicine": "Different medicine", "unknown": "SKU name not readable"}
EXP_ALLOC = {"outright_expired": "Outright expired", "near_expiry_lt_3m": "Near expiry (<3 months)",
             "shelf_life_ge_3m": ">=3 months in allocation", "undetermined": "Not determinable"}
EXP_IMG = {"received_item_expired": "Received item already expired", "received_near_expiry_lt_3m": "Received item near expiry (<3 months)",
           "received_item_ok": "Received item has >=3 months", "batch_only_no_expiry_read": "Batch read, expiry not legible",
           "cx_image_unclear": "CX image not clear", "no_images_read": "Photo not read yet"}


def _raised(r, nc_by_order):
    """-> (bucket1, bucket2, bucket3, evidence basis, confidence, photos_read)"""
    c = r["category"]
    if c == "Missing/Wrong Qty":
        m = ((r.get("extra") or {}).get("missing")) or {}
        basis = {"return_item": "Return item quantities", "ticket_text": "Ticket text",
                 "default_no_detail": "Default (no detail)"}.get(m.get("basis"), "")
        return ("SKU missing" if m.get("kind") == "sku_missing" else "Item missing", "", "", basis,
                "Likely" if m.get("basis") != "default_no_detail" else "Default", "No")
    if c == "Wrong Medicines":
        es = r.get("wrong_med") or []
        if not es:
            return ("Photo not read yet", "", "", "", "", "No")
        order = ["different_medicine", "same_brand_variant", "same_product_diff_packaging", "same_sku_consistent",
                 "other_order_line_photographed", "unknown"]
        e = sorted(es, key=lambda x: order.index(x["relation_type"]) if x["relation_type"] in order else 9)[0]
        b2 = ""
        if e["relation_type"] in ("different_medicine", "same_brand_variant"):
            br = e.get("bin_relation") or ""
            if br.startswith("picking_error"):
                b2 = "Bin link (picking error)"
            elif (e.get("batch_shared_orders") or 0) > 1:
                b2 = "Batch shared with ordered line"
            elif br in ("no_bin_link",):
                b2 = "No structural link"
            elif br in ("candidate_unverified", "unknown", ""):
                b2 = "Bin not assessed"
        b3 = (e.get("received") or "")[:80]
        return (WM.get(e["relation_type"], e["relation_type"]), b2, b3, "Photo read (received SKU name)",
                "Confirmed (owner)" if e.get("source") == "owner" else "Likely", "Yes")
    if c == "Expiry Issue":
        ex = r.get("expiry") or {}
        ic = ex.get("image_check") or {}
        v = ex.get("verdict") or "undetermined"
        iv = ic.get("image_verdict") or "no_images_read"
        b3 = "Batch/expiry differs from allocation" if (ic.get("batch_differs_from_allocation") or ic.get("same_batch_different_expiry")) else ""
        return (EXP_ALLOC.get(v, v), EXP_IMG.get(iv, iv), b3, "Allocation expiry vs delivery" + ("; photo read" if iv != "no_images_read" else ""),
                "Likely" if iv != "no_images_read" else "Allocation only", "Yes" if iv != "no_images_read" else "No")
    if c == "Damaged/Defective":
        d = ((r.get("extra") or {}).get("damaged")) or {}
        cold = bool(d.get("cold"))
        log = "Logistics exception recorded" if d.get("logistics_exception") else "No logistics exception (undetermined)"
        if cold:
            return ("Cold chain", "Not image-read (temperature complaint)", log, "Drug cold flag", "Flag", "No")
        k = nc_by_order.get(r["order_id"])
        return ("Non-cold", BUCKET_LABEL.get(k, "Photo not read yet") if k else "Photo not read yet", log,
                "Photo read" if k else "Drug cold flag", "Likely" if k else "Flag", "Yes" if k else "No")
    if c == "Switch Orders":
        s = ((r.get("extra") or {}).get("swap")) or {}
        return ("Order swap", "Label shows another order" if s else "", "", "Courier label read" if s else "", "Likely" if s else "", "Yes" if s else "No")
    return (CAT.get(c, c), "", "", "", "", "No")


def main():
    rca = json.loads((HERE / "rca.json").read_text())
    nc = json.loads((RAW / "rca_damaged_noncold.json").read_text())
    pri = {k: i for i, (k, _, _) in enumerate(BUCKETS)}
    nc_by_order = {}
    for o, _n, k, _note in nc["lines"]:
        k = bucket(k)
        if int(o) not in nc_by_order or pri[k] < pri[nc_by_order[int(o)]]:
            nc_by_order[int(o)] = k

    rows = []
    for r in rca["rows"]:
        b1, b2, b3, basis, conf, photos = _raised(r, nc_by_order)
        rows.append([
            r["order_id"], r["ticket_id"], r["date"], r["location"], CAT.get(r["category"], r["category"]),
            DECISION.get(r["decision"], r["decision"]),
            ND.get(r["no_decision_reason"], "") if r["decision"] == "no_decision" else "",
            RET.get(r["return_state"], ""), r["dependency"],
            b1, b2, b3, basis, conf, photos, "Yes" if r["in_t2"] else "No (held back, WH not yet commented)",
        ])
    out = {"generated_at": rca["generated_at"], "t2_cap_date": rca["t2_cap_date"], "columns": COLUMNS, "rows": rows,
           "note": "One row per order (first ticket wins). Trailing 90 days. Built by pipeline/build_rca_export.py"}
    (HERE / "rca_export.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    from collections import Counter
    print(f"rca_export.json: {len(rows)} rows x {len(COLUMNS)} columns")
    print("  issue:", dict(Counter(x[4] for x in rows)))
    print("  inv1 :", dict(Counter(x[5] for x in rows)))


if __name__ == "__main__":
    main()
