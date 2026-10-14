"""
Single definition of the RCA view (Tab 7 on the website AND the Google Sheet's "RCA view" tab).

The view is a pure function of the order-level export (rca_export.json): each row is a declarative filter
over export columns, AND-ed. The same spec is evaluated here (Python -> rca_trend.json) and in Apps Script
(gsheet/Code.gs, reads rca_view_spec.json), so website and sheet cannot drift apart.

where = list of (column, op, values) with op in {"in", "not_in"}.
"""
import json
from datetime import datetime
from pathlib import Path

from damaged_buckets import BUCKETS

HERE = Path(__file__).parent
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

I1, I2, RET = "Investigation bucket 1", "Investigation bucket 2", "Return request"
ISSUE, B1, B2, B3, BASIS = "Issue", "Raised bucket 1", "Raised bucket 2", "Raised bucket 3", "Evidence basis"
ND = ["Footage not available", "Batch not from our inventory", "CX image not clear", "Dependency not marked", "DocPharma order",
      "COGS < 100", "Agent mistake (WH marked, no WH comment)", "Return not received at WH", "Other WH note"]
UNREAD = "Photo not read yet"


def _w(*conds):
    return [list(c) for c in conds]


def build_layout():
    nd = [(I1, "in", ["No decision"])]
    L = []

    def add(key, label, sub, parent, indent, head, where):
        L.append({"key": key, "label": label, "sub": sub, "parent": parent, "indent": indent, "head": head, "where": _w(*where)})

    add("raised", "Tickets raised", "all categories", None, 0, True, [])
    add("accepted", "WH Accepted", "of raised", "raised", 0, False, [(I1, "in", ["Accepted"])])
    add("rejected", "WH Rejected", "of raised", "raised", 0, False, [(I1, "in", ["Rejected"])])
    add("no_decision", "No decision", "of raised", "raised", 0, False, nd)
    for n in ND:
        add("nd_" + n, "↳ " + n, "of no decision", "no_decision", 1, False, nd + [(I2, "in", [n])])
    add("nds_raised", "↳ return raised", "of no decision", "no_decision", 1, False, nd + [(RET, "in", ["Raised"])])
    add("nds_cancelled", "↳ return cancelled", "of no decision", "no_decision", 1, False, nd + [(RET, "in", ["Cancelled"])])
    add("nds_not_raised", "↳ return request not raised", "of no decision", "no_decision", 1, False, nd + [(RET, "in", ["Not raised"])])
    add("not_yet_read", "Not yet read", "no WH verdict cached yet", "raised", 0, False, [(I1, "in", ["Not yet read"])])

    WM = [(ISSUE, "in", ["Wrong medicine"])]
    add("wm", "Wrong medicine", "tickets", "raised", 0, True, WM)
    add("wm_read", "↳ photo read", "received SKU name read", "wm", 1, False, WM + [(B1, "not_in", [UNREAD])])
    add("wm_unread", "↳ photo not read yet", "", "wm", 1, False, WM + [(B1, "in", [UNREAD])])
    add("wm_same", "↳ photo shows the ordered SKU", "complaint not supported", "wm_read", 1, False,
        WM + [(B1, "in", ["Photo shows the ordered SKU", "Photo shows another line of the order"])])
    add("wm_variant", "↳ same medicine, different pack form", "same brand, other strength / pack / form", "wm_read", 1, False,
        WM + [(B1, "in", ["Same medicine, different pack form"])])
    add("wm_diff", "↳ different medicine", "", "wm_read", 1, False, WM + [(B1, "in", ["Different medicine"])])
    add("wm_undet", "↳ SKU name not readable", "", "wm_read", 1, False, WM + [(B1, "in", ["SKU name not readable"])])
    diff = WM + [(B1, "in", ["Different medicine"])]
    add("wm_bin", "   ↳ bin link (picking error)", "same bin / rack / nearby", "wm_diff", 2, False,
        diff + [(B2, "in", ["Bin link (picking error)", "Bin link + batch shared"])])
    add("wm_batch", "   ↳ batch shared with ordered line", "", "wm_diff", 2, False,
        diff + [(B2, "in", ["Batch shared with ordered line", "Bin link + batch shared"])])

    EX = [(ISSUE, "in", ["Expiry"])]
    add("ex", "Expiry", "tickets", "raised", 0, True, EX)
    add("ex_alloc_out", "↳ outright expired (allocation)", "allocation split - these 4 add up to Expiry", "ex", 1, False, EX + [(B1, "in", ["Outright expired"])])
    add("ex_alloc_near", "↳ near expiry <3 months (allocation)", "", "ex", 1, False, EX + [(B1, "in", ["Near expiry (<3 months)"])])
    add("ex_alloc_ok", "↳ >=3 months in allocation", "complaint not supported by allocation", "ex", 1, False, EX + [(B1, "in", [">=3 months in allocation"])])
    add("ex_alloc_undet", "↳ allocation not determinable", "no expiry return line / delivery date", "ex", 1, False, EX + [(B1, "in", ["Not determinable"])])
    add("ex_read", "↳ photo read", "photo split - read + not read add up to Expiry", "ex", 1, False, EX + [(B2, "not_in", [UNREAD])])
    add("ex_unread", "↳ photo not read yet", "", "ex", 1, False, EX + [(B2, "in", [UNREAD])])
    exr = EX + [(B2, "not_in", [UNREAD])]
    add("ex_img_expired", "   ↳ received item already expired", "printed expiry before delivery", "ex_read", 2, False, EX + [(B2, "in", ["Received item already expired"])])
    add("ex_img_near", "   ↳ received item near expiry <3 months", "", "ex_read", 2, False, EX + [(B2, "in", ["Received item near expiry (<3 months)"])])
    add("ex_img_ok", "   ↳ received item has >=3 months", "photo supports the allocation", "ex_read", 2, False, EX + [(B2, "in", ["Received item has >=3 months"])])
    add("ex_img_batchonly", "   ↳ batch read, expiry not legible", "", "ex_read", 2, False, EX + [(B2, "in", ["Batch read, expiry not legible"])])
    add("ex_img_unclear", "   ↳ CX image not clear", "", "ex_read", 2, False, EX + [(B2, "in", ["CX image not clear"])])
    add("ex_diff", "   memo: batch / expiry differs from allocation", "overlaps the rows above - not additive", "ex_read", 2, False,
        EX + [(B3, "in", ["Batch/expiry differs from allocation"])])

    DM = [(ISSUE, "in", ["Damaged"])]
    add("dm", "Damaged", "tickets", "raised", 0, True, DM)
    add("dm_cold", "↳ cold chain", "temperature complaint - photos not read", "dm", 1, False, DM + [(B1, "in", ["Cold chain"])])
    add("dm_nc", "↳ non-cold", "", "dm", 1, False, DM + [(B1, "in", ["Non-cold"])])
    nc = DM + [(B1, "in", ["Non-cold"])]
    add("dm_nc_read", "   ↳ photo read", "the buckets below add up to this", "dm_nc", 2, False, nc + [(B2, "not_in", [UNREAD])])
    add("dm_nc_unread", "   ↳ photo not read yet", "", "dm_nc", 2, False, nc + [(B2, "in", [UNREAD])])
    for k, lab, wh in BUCKETS:
        add("dmb_" + k, "      ↳ " + lab, wh, "dm_nc_read", 3, False, nc + [(B2, "in", [lab])])
    add("dm_nc_log", "memo: non-cold with a logistics exception", "NDR / repeat attempt - overlaps the rows above, not additive", "dm_nc", 1, False,
        nc + [(B3, "in", ["Logistics exception recorded"])])

    MQ = [(ISSUE, "in", ["Missing / short quantity"])]
    add("mq", "Missing / short quantity", "tickets", "raised", 0, True, MQ)
    add("mq_sku", "↳ SKU missing", "whole line / empty box / not received - the 2 rows add up to the total", "mq", 1, False, MQ + [(B1, "in", ["SKU missing"])])
    add("mq_item", "↳ item missing", "partial quantity", "mq", 1, False, MQ + [(B1, "in", ["Item missing"])])
    add("mq_text", "memo: classified from the ticket text", "no return item - overlaps the 2 rows above", "mq", 1, False, MQ + [(BASIS, "in", ["Ticket text"])])
    add("mq_default", "memo: default to item missing", "no return item and no detail in the ticket - overlaps the 2 rows above", "mq", 1, False,
        MQ + [(BASIS, "in", ["Default (no detail)"])])
    add("sw", "Order swap", "tickets", "raised", 0, True, [(ISSUE, "in", ["Order swap"])])
    add("mrp", "MRP / batch mismatch", "tickets (new sub-disposition)", "raised", 0, True, [(ISSUE, "in", ["MRP / batch mismatch"])])
    return L


def _match(row, col, where):
    for c, op, vals in where:
        v = row[col[c]]
        if (op == "in") != (v in vals):
            return False
    return True


def evaluate(export, layout):
    """export dict (rca_export.json) + layout -> rca_trend.json structure."""
    col = {c: i for i, c in enumerate(export["columns"])}
    cutoff = export["t2_cap_date"]
    dcol = col["Created date"]
    rows = [r for r in export["rows"] if r[dcol] <= cutoff]
    days = sorted({r[dcol] for r in rows})
    by_day = {}
    for r in rows:
        by_day.setdefault(r[dcol], []).append(r)

    cache = {}

    def counts(item):
        k = item["key"]
        if k not in cache:
            cache[k] = {d: sum(1 for r in by_day.get(d, []) if _match(r, col, item["where"])) for d in days}
        return cache[k]

    items = {it["key"]: it for it in layout}

    def cell(item, day_list):
        n = sum(counts(item)[d] for d in day_list)
        if item["parent"] is None:
            return {"n": n, "text": str(n)}
        den = sum(counts(items[item["parent"]])[d] for d in day_list)
        pct = f"{round(100 * n / den)}%" if den else "–"
        return {"n": n, "of": den, "pct": pct, "text": f"{n} | {pct}"}

    out = []
    for it in layout:
        out.append({"label": it["label"], "sub": it["sub"] or None, "kind": "wfr_pto" if it["head"] else "plain", "indent": it["indent"],
                    "3mo": cell(it, days), "1mo": cell(it, days[-30:]), "2wk": cell(it, days[-14:]),
                    "daily": {d: cell(it, [d]) for d in days}})
    labels = {d: f"{int(d[8:10])} {MONTHS[int(d[5:7]) - 1]}" for d in days}
    held = len(export["rows"]) - len(rows)
    return {"days": days, "day_labels": labels, "rows": out, "as_of": export["generated_at"][:10], "t2_cutoff": cutoff, "excluded_tickets": held}


def write_spec(path=HERE / "rca_view_spec.json"):
    Path(path).write_text(json.dumps({"layout": build_layout()}, ensure_ascii=False, separators=(",", ":")))
