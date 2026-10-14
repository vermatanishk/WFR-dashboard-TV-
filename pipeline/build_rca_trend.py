"""
Day-wise RCA view -> pipeline/rca_trend.json (Tab 7). Same pattern and cell format as the Everything
tab's macro trend table: frozen Metric | 3 month | last month | last 2 weeks, then one column per day,
most recent complete day first, T-2 capped (IST date of the data pull minus 2 days, bucketed by the UTC
date of `created_time`, exactly like build_macro_trend.py).

Each cell is "count | % of its parent row" ("–" when the parent is 0). Parent is the row's `of`:
Raised for the investigation funnel, the category total for the issue tree.

Rows are the RCA tree. Image-derived rows (wrong-medicine relation, expiry photo, damaged buckets) only
count tickets whose photos have been read (`read` rows give the coverage); "Not read" is never folded in.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from damaged_buckets import BUCKETS, bucket

HERE = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ND_LABEL = {"footage_missing": "Footage not available", "batch_not_in_inventory": "Batch not from our inventory",
            "cx_image_unclear": "CX image not clear", "dependency_not_marked": "Dependency not marked",
            "docpharma": "DocPharma order", "cogs_lt_100": "COGS < 100", "agent_mistake": "Agent mistake (WH marked, no WH comment)",
            "return_not_received_at_wh": "Return not received at WH", "other_wh_note": "Other WH note"}


def day_label(d):
    y, m, day = d.split("-")
    return f"{int(day)} {MONTHS[int(m) - 1]}"


def main():
    data = json.loads((HERE / "data.json").read_text())
    rca = json.loads((HERE / "rca.json").read_text())
    nc = json.loads((HERE / "zoho_raw90/rca_damaged_noncold.json").read_text())
    pri = {k: i for i, (k, _, _) in enumerate(BUCKETS)}
    nc_by_order = {}
    for o, _n, k, _note in nc["lines"]:
        k = bucket(k)
        if int(o) not in nc_by_order or pri[k] < pri[nc_by_order[int(o)]]:
            nc_by_order[int(o)] = k

    as_of = datetime.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(IST).date()
    cutoff = (as_of - timedelta(days=2)).isoformat()
    rows = [r for r in rca["rows"] if r["date"] <= cutoff]
    held = len(rca["rows"]) - len(rows)
    days = sorted({r["date"] for r in rows})

    def wm_rel(r):
        es = r.get("wrong_med") or []
        if not es:
            return None
        rels = {e["relation_type"] for e in es}
        for k in ("different_medicine", "same_brand_variant", "same_product_diff_packaging", "same_sku_consistent", "other_order_line_photographed"):
            if k in rels:
                return k
        return "unknown"

    def exp_vals(r):
        e = r.get("expiry") or {}
        ic = e.get("image_check") or {}
        return e.get("verdict"), ic.get("image_verdict"), ic

    # predicates ---------------------------------------------------------
    P = {}
    cat = lambda c: (lambda r: r["category"] == c)
    P["raised"] = lambda r: True
    for k in ("accepted", "rejected", "no_decision", "not_yet_read"):
        P[k] = (lambda k: lambda r: r["decision"] == k)(k)
    for k in ND_LABEL:
        P["nd_" + k] = (lambda k: lambda r: r["decision"] == "no_decision" and r["no_decision_reason"] == k)(k)
    for k in ("not_raised", "cancelled", "raised"):
        P["nds_" + k] = (lambda k: lambda r: r["decision"] == "no_decision" and r["return_state"] == k)(k)

    P["wm"] = cat("Wrong Medicines")
    P["wm_read"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) is not None
    P["wm_unread"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) is None
    P["wm_undet"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) == "unknown"
    P["wm_same"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) in ("same_sku_consistent", "other_order_line_photographed")
    P["wm_variant"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) in ("same_brand_variant", "same_product_diff_packaging")
    P["wm_diff"] = lambda r: r["category"] == "Wrong Medicines" and wm_rel(r) == "different_medicine"
    P["wm_bin"] = lambda r: r["category"] == "Wrong Medicines" and any(
        (e.get("bin_relation") or "").startswith("picking_error") for e in (r.get("wrong_med") or []) if e["relation_type"] in ("different_medicine", "same_brand_variant"))
    P["wm_batch"] = lambda r: r["category"] == "Wrong Medicines" and any(
        (e.get("batch_shared_orders") or 0) > 1 for e in (r.get("wrong_med") or []))

    P["ex"] = cat("Expiry Issue")
    P["ex_alloc_out"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[0] == "outright_expired"
    P["ex_alloc_near"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[0] == "near_expiry_lt_3m"
    P["ex_alloc_ok"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[0] == "shelf_life_ge_3m"
    P["ex_alloc_undet"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[0] not in ("outright_expired", "near_expiry_lt_3m", "shelf_life_ge_3m")
    P["ex_unread"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] in (None, "no_images_read")
    P["ex_img_ok"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] == "received_item_ok"
    P["ex_img_batchonly"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] == "batch_only_no_expiry_read"
    P["ex_read"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] not in (None, "no_images_read")
    P["ex_img_expired"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] == "received_item_expired"
    P["ex_img_near"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] == "received_near_expiry_lt_3m"
    P["ex_diff"] = lambda r: r["category"] == "Expiry Issue" and bool(exp_vals(r)[2].get("batch_differs_from_allocation") or exp_vals(r)[2].get("same_batch_different_expiry"))
    P["ex_img_unclear"] = lambda r: r["category"] == "Expiry Issue" and exp_vals(r)[1] == "cx_image_unclear"

    P["dm"] = cat("Damaged/Defective")
    P["dm_cold"] = lambda r: r["category"] == "Damaged/Defective" and bool((r.get("extra") or {}).get("damaged", {}).get("cold"))
    P["dm_nc"] = lambda r: r["category"] == "Damaged/Defective" and not (r.get("extra") or {}).get("damaged", {}).get("cold")
    P["dm_nc_log"] = lambda r: P["dm_nc"](r) and bool((r.get("extra") or {}).get("damaged", {}).get("logistics_exception"))
    P["dm_nc_read"] = lambda r: P["dm_nc"](r) and r["order_id"] in nc_by_order
    P["dm_nc_unread"] = lambda r: P["dm_nc"](r) and r["order_id"] not in nc_by_order
    for k, _l, _w in BUCKETS:
        P["dmb_" + k] = (lambda k: lambda r: P["dm_nc"](r) and nc_by_order.get(r["order_id"]) == k)(k)

    P["mq"] = cat("Missing/Wrong Qty")
    P["mq_sku"] = lambda r: r["category"] == "Missing/Wrong Qty" and ((r.get("extra") or {}).get("missing") or {}).get("kind") == "sku_missing"
    P["mq_text"] = lambda r: r["category"] == "Missing/Wrong Qty" and ((r.get("extra") or {}).get("missing") or {}).get("basis") == "ticket_text"
    P["mq_default"] = lambda r: r["category"] == "Missing/Wrong Qty" and ((r.get("extra") or {}).get("missing") or {}).get("basis") == "default_no_detail"
    P["mq_item"] = lambda r: r["category"] == "Missing/Wrong Qty" and ((r.get("extra") or {}).get("missing") or {}).get("kind") == "item_missing"
    P["sw"] = cat("Switch Orders")
    P["mrp"] = cat("MRP/Batch Mismatch")

    # layout: (key, label, sub, parent_key, indent_level, highlight)
    L = [
        ("raised", "Tickets raised", "all categories", None, 0, True),
        ("accepted", "WH Accepted", "of raised", "raised", 0, False),
        ("rejected", "WH Rejected", "of raised", "raised", 0, False),
        ("no_decision", "No decision", "of raised", "raised", 0, False),
    ] + [("nd_" + k, "↳ " + v, "of no decision", "no_decision", 1, False) for k, v in ND_LABEL.items()] + [
        ("nds_raised", "↳ return raised", "of no decision", "no_decision", 1, False),
        ("nds_cancelled", "↳ return cancelled", "of no decision", "no_decision", 1, False),
        ("nds_not_raised", "↳ return request not raised", "of no decision", "no_decision", 1, False),
        ("not_yet_read", "Not yet read", "no WH verdict cached yet", "raised", 0, False),

        ("wm", "Wrong medicine", "tickets", "raised", 0, True),
        ("wm_read", "↳ photo read", "received SKU name read", "wm", 1, False),
        ("wm_unread", "↳ photo not read yet", "", "wm", 1, False),
        ("wm_same", "↳ photo shows the ordered SKU", "complaint not supported", "wm_read", 1, False),
        ("wm_variant", "↳ same medicine, different pack form", "same brand, other strength / pack / form", "wm_read", 1, False),
        ("wm_diff", "↳ different medicine", "", "wm_read", 1, False),
        ("wm_undet", "↳ SKU name not readable", "", "wm_read", 1, False),
        ("wm_bin", "   ↳ bin link (picking error)", "same bin / rack / nearby", "wm_diff", 2, False),
        ("wm_batch", "   ↳ batch shared with ordered line", "", "wm_diff", 2, False),

        ("ex", "Expiry", "tickets", "raised", 0, True),
        ("ex_alloc_out", "↳ outright expired (allocation)", "allocation split - these 4 add up to Expiry", "ex", 1, False),
        ("ex_alloc_near", "↳ near expiry <3 months (allocation)", "", "ex", 1, False),
        ("ex_alloc_ok", "↳ >=3 months in allocation", "complaint not supported by allocation", "ex", 1, False),
        ("ex_alloc_undet", "↳ allocation not determinable", "no expiry return line / delivery date", "ex", 1, False),
        ("ex_read", "↳ photo read", "photo split - read + not read add up to Expiry", "ex", 1, False),
        ("ex_unread", "↳ photo not read yet", "", "ex", 1, False),
        ("ex_img_expired", "   ↳ received item already expired", "printed expiry before delivery", "ex_read", 2, False),
        ("ex_img_near", "   ↳ received item near expiry <3 months", "", "ex_read", 2, False),
        ("ex_img_ok", "   ↳ received item has >=3 months", "photo supports the allocation", "ex_read", 2, False),
        ("ex_img_batchonly", "   ↳ batch read, expiry not legible", "", "ex_read", 2, False),
        ("ex_img_unclear", "   ↳ CX image not clear", "", "ex_read", 2, False),
        ("ex_diff", "   memo: batch / expiry differs from allocation", "overlaps the rows above - not additive", "ex_read", 2, False),

        ("dm", "Damaged", "tickets", "raised", 0, True),
        ("dm_cold", "↳ cold chain", "temperature complaint - photos not read", "dm", 1, False),
        ("dm_nc", "↳ non-cold", "", "dm", 1, False),
        ("dm_nc_read", "   ↳ photo read", "the buckets below add up to this", "dm_nc", 2, False),
        ("dm_nc_unread", "   ↳ photo not read yet", "", "dm_nc", 2, False),
    ] + [("dmb_" + k, "      ↳ " + lab, wh, "dm_nc_read", 3, False) for k, lab, wh in BUCKETS] + [

        ("dm_nc_log", "memo: non-cold with a logistics exception", "NDR / repeat attempt - overlaps the rows above, not additive", "dm_nc", 1, False),

        ("mq", "Missing / short quantity", "tickets", "raised", 0, True),
        ("mq_sku", "↳ SKU missing", "whole line / empty box / not received - the 2 rows add up to the total", "mq", 1, False),
        ("mq_item", "↳ item missing", "partial quantity", "mq", 1, False),
        ("mq_text", "memo: classified from the ticket text", "no return item - overlaps the 2 rows above", "mq", 1, False),
        ("mq_default", "memo: default to item missing", "no return item and no detail in the ticket - overlaps the 2 rows above", "mq", 1, False),

        ("sw", "Order swap", "tickets", "raised", 0, True),
        ("mrp", "MRP / batch mismatch", "tickets (new sub-disposition)", "raised", 0, True),
    ]

    def cnt(key, day_list):
        s = set(day_list)
        f = P[key]
        return sum(1 for r in rows if r["date"] in s and f(r))

    def cell(key, parent, day_list):
        n = cnt(key, day_list)
        if parent is None:
            return {"n": n, "text": f"{n}"}
        d = cnt(parent, day_list)
        pct = f"{round(100 * n / d)}%" if d else "–"
        return {"n": n, "of": d, "pct": pct, "text": f"{n} | {pct}"}

    def window(n):
        return days[-n:]

    out_rows = []
    for key, label, sub, parent, ind, hl in L:
        out_rows.append({"label": label, "sub": sub or None, "kind": "wfr_pto" if hl else "plain", "indent": ind,
                         "3mo": cell(key, parent, days), "1mo": cell(key, parent, window(30)), "2wk": cell(key, parent, window(14)),
                         "daily": {d: cell(key, parent, [d]) for d in days}})
    (HERE / "rca_trend.json").write_text(json.dumps({
        "days": days, "day_labels": {d: day_label(d) for d in days}, "rows": out_rows,
        "as_of": as_of.isoformat(), "t2_cutoff": cutoff, "excluded_tickets": held}))
    print(f"rca_trend.json: {len(days)} days, {len(out_rows)} rows, through {cutoff}, held back {held}")
    for r in out_rows[:6]:
        print(" ", r["label"], r["3mo"]["text"])


if __name__ == "__main__":
    main()
