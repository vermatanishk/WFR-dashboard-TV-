"""
Warehouse self-reported error log ("Pan India errors sheets", Google Sheet 1uDa_W4mPkiWnr5y8xckobhbJ3fW_pvnFDfFPzxqdhHo, live tab "October" = gid 128620232)
-> zoho_raw90/wh_error_log.json  {order_id: {entries: [{date, reason, type, qty, sku, sent, wh, by}], first_date}}   (owner, 2026-11-27)

Every row is the Warehouse team itself saying "we made this mistake" on an order: an explicit admission, so it counts as WH accepted:
  * every complaint-type Zoho ticket of the order gets an `admitted` verdict (source `wh_error_log`) in wh_text_check.json - Tab 1, the EOD tab,
    the complaint baseline and RCA all read that cache, so one write reaches every layer. `admitted` is never downgraded (recheck / ingest keep it,
    audit_admitted.py skips source wh_error_log).
  * build_complaints.py also flags complaint rows of a logged order (column "WH error log") so an order WITHOUT a complaint-type ticket still counts accepted.
The log is cumulative (never deletes). Refresh: download the Drive sheet as CSV (Drive MCP download_file_content, text/csv = the live tab), then
    python3 pipeline/wh_error_log.py <csv>        # merge + apply to the verdict cache
    python3 pipeline/wh_error_log.py              # re-apply only
CSV columns: Date(dd-mm-yyyy), Order id, customer SKU, SKU packed, Qty, Reason, Warehouse, Error done by, ...
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
LOG = RAW / "wh_error_log.json"
REASON_TYPE = {"short qty": "Missing / short qty", "short qty no footage": "Missing / short qty", "excess": "Missing / short qty",
               "wrong sku": "Wrong medicine", "switch order": "Order swap", "batch issue": "MRP / batch mismatch", "wrong mrp": "MRP / batch mismatch",
               "damaged": "Damage"}


def load():
    return json.loads(LOG.read_text()) if LOG.exists() else {}


def merge(csv_path):
    log = load()
    n = 0
    for x in list(csv.reader(open(csv_path)))[1:]:
        if len(x) < 8 or not x[0].strip() or not x[1].strip().isdigit():
            continue
        d, m, y = x[0].strip().split("-")
        reason = x[5].strip()
        e = {"date": f"{y}-{m}-{d}", "reason": reason, "type": REASON_TYPE.get(reason.lower()), "qty": x[4].strip(), "sku": x[2].strip(),
             "sent": x[3].strip(), "wh": x[6].strip(), "by": x[7].strip()}
        rec = log.setdefault(x[1].strip(), {"entries": [], "first_date": e["date"]})
        if e not in rec["entries"]:
            rec["entries"].append(e)
            n += 1
        rec["first_date"] = min(rec["first_date"], e["date"])
    LOG.write_text(json.dumps(log, separators=(",", ":"), sort_keys=True))
    print(f"error log: {len(log)} orders, {n} new entries")
    return log


def order_tickets():
    """order id -> {ticket id: complaint type} for complaint-type tickets, from the complaint pull and the dashboard dataset."""
    from build_complaints import parse_order_id, sub_type
    from category_mapping import CATEGORY_MAP
    out = {}
    z = json.loads((RAW / "cmp_zoho_tickets.json").read_text())["days"]
    for ts in z.values():
        for t in ts:
            o, ty = parse_order_id(t["order_raw"]), sub_type(t["sub_disposition"])
            if o and ty:
                out.setdefault(o, {})[t["ticket_id"]] = ty
    ctype = {"Missing/Wrong Qty": "Missing / short qty", "Wrong Medicines": "Wrong medicine", "Expiry Issue": "Expiry", "Damaged/Defective": "Damage",
             "Switch Orders": "Order swap", "MRP/Batch Mismatch": "MRP / batch mismatch"}
    for t in json.loads((HERE / "data.json").read_text())["tickets"]:
        out.setdefault(t["order_id"], {}).setdefault(str(t["ticket_id"]), ctype.get(t["category"]))
    return out


def target_tickets(tickets, log_type):
    """Tickets of the order the logged error applies to: same complaint type; if the order has none, its other WFR-type tickets
    (never Order swap / Damage ones - the swap attribution and damage views are separate and must not change on a short-qty log line)."""
    same = [t for t, ty in tickets.items() if ty == log_type]
    if same or log_type is None:
        return same
    return [t for t, ty in tickets.items() if ty in ("Missing / short qty", "Wrong medicine", "Expiry", "MRP / batch mismatch")]


def refresh_scope(log):
    """Owner rule (2026-11-27): a logged order whose return was cancelled by the customer / rejected at QC is NOT counted (same in-scope rule as the funnel).
    scope 'out' = every WFR complaint row of the order is out of scope. Updated from the current complaint export; values for older orders (before the export window,
    derived from the historic Jun-Nov rebuild) are kept."""
    p = HERE / "complaints_export.json"
    if not p.exists():
        return
    e = json.loads(p.read_text())
    C = {c: i for i, c in enumerate(e["columns"])}
    by = {}
    for r in e["rows"]:
        if r[C["Complaint type"]] in ("Wrong medicine", "Missing / short qty", "Expiry", "MRP / batch mismatch"):
            by.setdefault(str(r[0]), []).append(r[C["In scope"]])
    for o, rec in log.items():
        if o in by:
            rec["scope"] = "out" if all(x == "No" for x in by[o]) else "in"


def apply(log=None):
    log = log or load()
    refresh_scope(log)
    LOG.write_text(json.dumps(log, separators=(",", ":"), sort_keys=True))
    cache_p = RAW / "wh_text_check.json"
    cache = json.loads(cache_p.read_text())
    ot = order_tickets()
    new = changed = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for o, rec in log.items():
        if rec.get("scope") == "out":
            continue                      # return cancelled / QC-rejected: not counted
        e = rec["entries"][0]
        for tid in sorted(target_tickets(ot.get(int(o), {}), e["type"])):
            old = cache.get(tid)
            if old and old.get("verdict") == "admitted":
                continue
            ev = f"Warehouse error log ({e['date']}, {e['reason']}, {e['wh'] or 'WH n/a'}): the Warehouse team logged this order as its own mistake"
            cache[tid] = {"verdict": "admitted", "evidence": ev, "reason": "Warehouse self-reported error log (explicit admission)", "order_id": int(o),
                          "admitted": True, "source": "wh_error_log", "rechecked_on": today, "previous_verdict": (old or {}).get("verdict")}
            new += 0 if old else 1
            changed += 1 if old else 0
    cache_p.write_text(json.dumps(cache))
    print(f"verdict cache: {new} tickets newly admitted, {changed} flipped from {{denied / no comment / other}} to admitted (source wh_error_log)")


if __name__ == "__main__":
    lg = merge(sys.argv[1]) if len(sys.argv) > 1 else None
    apply(lg)
