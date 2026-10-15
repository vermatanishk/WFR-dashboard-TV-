"""
Deterministic RCA evidence -> zoho_raw90/rca_expiry.json and rca_binmap.json,
keyed by ticket_id. Pure python over raw ClickHouse pulls saved in
zoho_raw90/ (this repo's convention: the refresh session runs the SQL through
the ClickHouse MCP and saves the rows; scripts never hold DB credentials).

Raw inputs (all keyed by customer-facing order_id, never marketplace_orders.id):
  rca_expiry_raw.jsonl - one row per (order_id, return-item drug_code):
      {"order_id","drug_code","reason","batches":["<batch>|<YYYY-MM-DD>",...],"delivered_at"}
      SQL (CDC-deduped with LIMIT 1 BY id, _peerdb_is_deleted=0):
        marketplace_return_items (reason != 'RTO') JOIN marketplace_return_request ON return_request_id=id
        LEFT JOIN marketplace_order_item_batches ON order_id AND master_drug_code=drug_code
        LEFT JOIN marketplace_order_status_log (current_status_id=70, min(created_at)) AS delivered_at
      `is_active` is NOT used - it is 0 on these rows.

EXPIRY RULES (user-defined 2026-10-14):
  1. Not expired but near expiry: shelf life at DELIVERY = allocated batch
     expiry - delivery date, bucketed `<3m` vs `>=3m`; expiry <= delivery is
     outright expired.
  2. Invoice batch vs batch actually received (image) - needs image
     extraction; this script only flags the tickets where the allocated batch
     does NOT support the complaint (`allocation_supports_complaint: false`),
     which is exactly the set that needs that image check.
Expiry dates are month-granular in the source (many rows are day 1 = the
printed MM/YYYY). A printed month is valid through the END of that month, so
a day-1 date is treated as end-of-month; `precision` records which was used.
"""
import json
import re
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"


def add_months(d, n):
    m = d.month - 1 + n
    y, mo = d.year + m // 12, m % 12 + 1
    return date(y, mo, min(d.day, monthrange(y, mo)[1]))


def effective_expiry(s):
    d = date.fromisoformat(s)
    if d.day == 1:  # month-granular print -> valid through month end
        return date(d.year, d.month, monthrange(d.year, d.month)[1]), "month"
    return d, "day"


def shelf_verdict(expiry_str, delivered):
    exp, prec = effective_expiry(expiry_str)
    if exp <= delivered:
        bucket = "outright_expired"
    elif exp < add_months(delivered, 3):
        bucket = "near_expiry_lt_3m"
    else:
        bucket = "shelf_life_ge_3m"
    return bucket, (exp - delivered).days, prec


MONTHS = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def parse_printed_expiry(s):
    """Expiry as printed on the pack/invoice (image-read string) -> (date, precision)
    or None. MM/YYYY, MM/YY, 'MMM YYYY', 'DD/MMM/YYYY', 'DD/MM/YYYY'. A month-only
    print is valid through the END of that month."""
    if not s:
        return None
    t = s.upper()
    m = re.search(r"\b(\d{1,2})/([A-Z]{3})/(\d{4})\b", t)
    if m and m.group(2) in MONTHS:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))), "day"
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", t)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), "day"
    m = re.search(r"\b(\d{1,2})/(\d{4})\b", t)
    if m:
        y, mo = int(m.group(2)), int(m.group(1))
        return date(y, mo, monthrange(y, mo)[1]), "month"
    m = re.search(r"\b(\d{1,2})/(\d{2})\b", t)
    if m:
        y, mo = 2000 + int(m.group(2)), int(m.group(1))
        return date(y, mo, monthrange(y, mo)[1]), "month"
    m = re.search(r"\b([A-Z]{3})[ -]?(\d{4})\b", t)
    if m and m.group(1) in MONTHS:
        y, mo = int(m.group(2)), MONTHS[m.group(1)]
        return date(y, mo, monthrange(y, mo)[1]), "month"
    return None


def _norm(b):
    return re.sub(r"[^A-Z0-9]", "", (b or "").upper())


def _edit(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def batch_vs_allocation(printed, allocated):
    """-> 'match' | 'near_match' (<=2 edits: OCR-level) | 'differs' | 'unknown'"""
    p = _norm(re.split(r"\(| AND ", printed or "")[0])
    if not p or "NONE" in p or not allocated:
        return "unknown"
    al = [_norm(a) for a in allocated]
    if p in al:
        return "match"
    return "near_match" if min(_edit(p, a) for a in al) <= 2 else "differs"


def image_expiry_check(items, delivered, images):
    """Compare what the customer's photos show with the allocated batch.
    images: image-read results for this order (rca_image_check.json rows).
    Image-derived, so strength is capped at 'likely'."""
    if not images:
        return {"image_verdict": "no_images_read"}
    allocated_b = [i["batch"] for i in items]
    allocated_e = [date.fromisoformat(i["expiry"]) for i in items]
    printed, legible = [], False
    for r in images:
        lg = r.get("legibility") or {}
        if lg.get("expiry") in ("high", "medium") or lg.get("batch") in ("high", "medium"):
            legible = True
        pe = parse_printed_expiry(r.get("expiry"))
        if not (pe or r.get("batch")):
            continue
        row = {"batch": r.get("batch"), "expiry_printed": r.get("expiry"),
               "batch_vs_allocation": batch_vs_allocation(r.get("batch"), allocated_b)}
        if pe and lg.get("expiry") in ("high", "medium"):
            exp, prec = pe
            row["bucket_at_delivery"] = ("outright_expired" if exp <= delivered else
                                         "near_expiry_lt_3m" if exp < add_months(delivered, 3) else "shelf_life_ge_3m")
            row["days_left_at_delivery"] = (exp - delivered).days
            if row["batch_vs_allocation"] in ("match", "near_match") and allocated_e and \
               abs((exp - min(allocated_e, key=lambda a: abs((a - exp).days))).days) > 45:
                row["same_batch_different_expiry"] = True
        printed.append(row)
    read_exp = [p for p in printed if "bucket_at_delivery" in p]
    if not legible or not printed:
        return {"image_verdict": "cx_image_unclear", "images_read": len(images), "printed": printed}
    worst = min(read_exp, key=lambda p: p["days_left_at_delivery"]) if read_exp else None
    out = {"images_read": len(images), "printed": printed, "strength": "likely"}
    if worst is None:
        out["image_verdict"] = "batch_only_no_expiry_read"
    else:
        out["image_verdict"] = {"outright_expired": "received_item_expired",
                                "near_expiry_lt_3m": "received_near_expiry_lt_3m",
                                "shelf_life_ge_3m": "received_item_ok"}[worst["bucket_at_delivery"]]
    out["batch_differs_from_allocation"] = any(p["batch_vs_allocation"] == "differs" for p in printed)
    out["same_batch_different_expiry"] = any(p.get("same_batch_different_expiry") for p in printed)
    return out


def expiry_for_order(rows, images=None):
    """rows: raw rows for one order. Picks the complained item(s) - return
    items whose reason mentions expiry - falling back to all return items."""
    exp_rows = [r for r in rows if "expir" in (r.get("reason") or "").lower()]
    use = exp_rows or rows
    items = []
    for r in use:
        delivered = datetime.fromisoformat(r["delivered_at"].replace("Z", "+00:00")).date() if r.get("delivered_at") else None
        for b in r["batches"]:
            batch, exp = b.split("|")
            if delivered is None:
                items.append({"drug_code": r["drug_code"], "batch": batch, "expiry": exp, "bucket": "no_delivery_date"})
                continue
            bucket, days, prec = shelf_verdict(exp, delivered)
            # sensitivity: the same batch read literally (day-1 NOT extended to month end)
            lit = date.fromisoformat(exp)
            lit_bucket = ("outright_expired" if lit <= delivered else
                          "near_expiry_lt_3m" if lit < add_months(delivered, 3) else "shelf_life_ge_3m")
            items.append({"drug_code": r["drug_code"], "batch": batch, "expiry": exp,
                          "bucket": bucket, "days_left_at_delivery": days, "precision": prec,
                          "bucket_if_day1_literal": lit_bucket})
    if not items:
        return {"verdict": "undetermined", "why": "no allocated batch / return item found for this order", "items": []}
    worst = min((i for i in items if "days_left_at_delivery" in i), key=lambda i: i["days_left_at_delivery"], default=None)
    if worst is None:
        return {"verdict": "undetermined", "why": "no delivered timestamp", "items": items}
    supports = worst["bucket"] in ("outright_expired", "near_expiry_lt_3m")
    deliv = datetime.fromisoformat(use[0]["delivered_at"].replace("Z", "+00:00")).date()
    return {
        "image_check": image_expiry_check(items, deliv, images or []),
        "verdict": worst["bucket"],
        "days_left_at_delivery": worst["days_left_at_delivery"],
        "allocation_supports_complaint": supports,
        "complaint_reason_is_expiry": bool(exp_rows),
        "strength": "strong" if supports else "supporting",
        "next_check": None if supports else "compare invoice batch/expiry with batch+expiry read off the customer image",
        "items": items,
    }


def main():
    data = json.loads((HERE / "data.json").read_text())
    by_order = {}
    p = RAW / "rca_expiry_raw.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                by_order.setdefault(r["order_id"], []).append(r)
    from image_reads import reads_by_order
    imgs = reads_by_order()
    out = {}
    for t in data["tickets"]:
        if t["category"] == "Expiry Issue":
            out[t["ticket_id"]] = (expiry_for_order(by_order[t["order_id"]], imgs.get(t["order_id"])) if t["order_id"] in by_order
                                   else {"verdict": "undetermined", "why": "no non-RTO return item for this order in ClickHouse (or order not in the pull) - cannot tell which drug was complained about", "items": []})
    (RAW / "rca_expiry.json").write_text(json.dumps(out))
    from collections import Counter
    print("expiry verdicts:", dict(Counter(v["verdict"] for v in out.values())))
    flip = sum(1 for v in out.values() if v.get("items") and v["verdict"] == "shelf_life_ge_3m"
               and any(i.get("bucket_if_day1_literal") != "shelf_life_ge_3m" for i in v["items"]))
    print("would flip to <3m if day-1 expiries were read literally:", flip)
    iv = Counter((v.get("image_check") or {}).get("image_verdict") for v in out.values() if v.get("items"))
    print("image verdicts:", dict(iv))
    print("batch differs from allocation:", sum(1 for v in out.values() if (v.get("image_check") or {}).get("batch_differs_from_allocation")),
          "| same batch, different expiry:", sum(1 for v in out.values() if (v.get("image_check") or {}).get("same_batch_different_expiry")))
    print("allocation does not support complaint:", sum(1 for v in out.values() if v.get("allocation_supports_complaint") is False))


if __name__ == "__main__":
    main()


# ---- Bin relation (picking-error attribution only) ----------------------------
#
# Owner-decided rule (2026-10-14): a wrong-medicine mix-up that has a bin link
# is attributed as a PICKING error only - there is no "layout error" label.
# The locations table (mdm_drug_warehouse_locations, SKU-level, warehouse-
# scoped) is the master. short_hand_location format: zone-vertical-rack-bin.
#   same bin              -> "picking_error", strength strong   (same bin: picker could not tell them apart)
#   same rack, other bin  -> "picking_error", strength supporting
#   same zone+vertical, other rack -> "picking_error_nearby", strength weak
#   anything else         -> "no_bin_link"
# Zone `UN` is the WH3 "unassigned" bucket - a placeholder, never a bin.
def bin_relation(loc_a, loc_b):
    """-> (relation, why, strength)"""
    if not loc_a or not loc_b:
        return "unknown", "missing location for one SKU", None
    a, b = loc_a.split("-"), loc_b.split("-")
    if len(a) != 4 or len(b) != 4:
        return "unknown", f"unparseable location {loc_a!r} / {loc_b!r}", None
    if a[0] == "UN" or b[0] == "UN":
        return "unknown", "SKU is in the UN (unassigned) zone - no real bin", None
    if a == b:
        return "picking_error", "same bin", "strong"
    if a[:3] == b[:3]:
        return "picking_error", "same rack, different bin", "supporting"
    if a[:2] == b[:2]:
        return "picking_error_nearby", "same zone and vertical, different rack", "weak"
    return "no_bin_link", "different zone/vertical", None
