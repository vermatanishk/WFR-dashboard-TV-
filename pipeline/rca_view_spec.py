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
NA = "Photo not available (no return request)"
NOT_READ = [UNREAD, NA]           # photo-split: read = not in this list
WINDOW_DAYS = 60                  # reporting scope (owner, 2026-10-26): trailing 60 days = 2 months
RET_STATES = ["Raised - Accepted & refunded", "Raised - Cancelled", "Raised - Rejected", "Raised - In progress", "Not raised"]


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
    add("not_yet_read", "Not yet read", "no WH verdict cached yet", "raised", 0, False, [(I1, "in", ["Not yet read"])])

    WM = [(ISSUE, "in", ["Wrong medicine"])]
    add("wm", "Wrong medicine", "tickets", "raised", 0, True, WM)
    add("wm_read", "↳ photo read", "received SKU name read", "wm", 1, False, WM + [(B1, "not_in", NOT_READ)])
    add("wm_unread", "↳ photo not read yet", "return raised, photo still to be read", "wm", 1, False, WM + [(B1, "in", [UNREAD])])
    add("wm_na", "↳ photo not available", "no return request, so no complaint photo exists", "wm", 1, False, WM + [(B1, "in", [NA])])
    add("wm_same", "↳ photo shows the ordered SKU", "complaint not supported", "wm_read", 1, False,
        WM + [(B1, "in", ["Photo shows the ordered SKU", "Photo shows another line of the order"])])
    add("wm_variant", "↳ same family medicine", "same brand, other strength / pack / form", "wm_read", 1, False,
        WM + [(B1, "in", ["Same family medicine"])])
    add("wm_diff", "↳ different medicine", "", "wm_read", 1, False, WM + [(B1, "in", ["Different medicine"])])
    add("wm_undet", "↳ not readable", "", "wm_read", 1, False, WM + [(B1, "in", ["Not readable"])])
    BINB = ["Bin link (picking error)", "Bin link + batch shared"]
    BATCHB = ["Batch shared with ordered line"]
    # Each wrong-SKU class is split MECE: bin picking issue (incl. bin + batch both) / batch sharing issue only / other
    for key, lab in (("variant", "same family medicine"), ("diff", "different medicine"), ("undet", "Not readable")):
        b1v = {"variant": "Same family medicine", "diff": "Different medicine", "undet": "Not readable"}[key]
        base = WM + [(B1, "in", [b1v])]
        add(f"wm_{key}_bin", "   ↳ bin picking issue", "same bin / rack / nearby (also when batch is shared)", f"wm_{key}", 2, False,
            base + [(B2, "in", BINB)])
        add(f"wm_{key}_batch", "   ↳ batch sharing issue", "ordered line's batch also sits on the received SKU, no bin link", f"wm_{key}", 2, False,
            base + [(B2, "in", BATCHB)])
        add(f"wm_{key}_other", "   ↳ other", "no structural link found / not assessable" + (" (SKU unreadable)" if key == "undet" else ""), f"wm_{key}", 2, False,
            base + [(B2, "not_in", BINB + BATCHB)])

    EX = [(ISSUE, "in", ["Expiry"])]
    add("ex", "Expiry", "tickets", "raised", 0, True, EX)
    add("ex_alloc_out", "↳ outright expired (allocation)", "allocation split - these 4 add up to Expiry", "ex", 1, False, EX + [(B1, "in", ["Outright expired"])])
    add("ex_alloc_near", "↳ near expiry <3 months (allocation)", "", "ex", 1, False, EX + [(B1, "in", ["Near expiry (<3 months)"])])
    add("ex_alloc_ok", "↳ >=3 months in allocation", "complaint not supported by allocation", "ex", 1, False, EX + [(B1, "in", [">=3 months in allocation"])])
    add("ex_alloc_undet", "↳ allocation not determinable", "no expiry return line / delivery date", "ex", 1, False, EX + [(B1, "in", ["Not determinable"])])
    add("ex_read", "↳ photo read", "photo split - read + not read + not available add up to Expiry", "ex", 1, False, EX + [(B2, "not_in", NOT_READ)])
    add("ex_unread", "↳ photo not read yet", "return raised, photo still to be read", "ex", 1, False, EX + [(B2, "in", [UNREAD])])
    add("ex_na", "↳ photo not available", "no return request, so no complaint photo exists", "ex", 1, False, EX + [(B2, "in", [NA])])
    add("ex_img_expired", "   ↳ received item already expired", "printed expiry before delivery", "ex_read", 2, False, EX + [(B2, "in", ["Received item already expired"])])
    add("ex_img_near", "   ↳ received item near expiry <3 months", "", "ex_read", 2, False, EX + [(B2, "in", ["Received item near expiry (<3 months)"])])
    add("ex_img_ok", "   ↳ received item has >=3 months", "photo supports the allocation", "ex_read", 2, False, EX + [(B2, "in", ["Received item has >=3 months"])])
    add("ex_img_batchonly", "   ↳ batch read, expiry not legible", "", "ex_read", 2, False, EX + [(B2, "in", ["Batch read, expiry not legible"])])
    add("ex_img_unclear", "   ↳ CX image not clear", "", "ex_read", 2, False, EX + [(B2, "in", ["CX image not clear"])])
    DIFF = ["Differs - received item expired", "Differs - received item not expired", "Differs - expiry not legible"]
    add("ex_diff", "   batch / expiry differs from allocation", "overlaps the photo outcomes above; split below adds to this", "ex_read", 2, False, EX + [(B3, "in", DIFF)])
    add("ex_diff_exp", "      ↳ received item expired", "", "ex_diff", 3, False, EX + [(B3, "in", [DIFF[0]])])
    add("ex_diff_notexp", "      ↳ received item not expired", "", "ex_diff", 3, False, EX + [(B3, "in", [DIFF[1]])])
    add("ex_diff_unk", "      ↳ expiry not legible", "", "ex_diff", 3, False, EX + [(B3, "in", [DIFF[2]])])

    DM = [(ISSUE, "in", ["Damaged"])]
    add("dm", "Damaged", "tickets", "raised", 0, True, DM)
    add("dm_cold", "↳ cold chain", "temperature complaint - photos not read", "dm", 1, False, DM + [(B1, "in", ["Cold chain"])])
    add("dm_nc", "↳ non-cold", "", "dm", 1, False, DM + [(B1, "in", ["Non-cold"])])
    nc = DM + [(B1, "in", ["Non-cold"])]
    add("dm_nc_read", "   ↳ photo read", "the buckets below add up to this", "dm_nc", 2, False, nc + [(B2, "not_in", NOT_READ)])
    add("dm_nc_unread", "   ↳ photo not read yet", "return raised, photo still to be read", "dm_nc", 2, False, nc + [(B2, "in", [UNREAD])])
    add("dm_nc_na", "   ↳ photo not available", "no return request, so no complaint photo exists", "dm_nc", 2, False, nc + [(B2, "in", [NA])])
    for k, lab, wh in BUCKETS:
        add("dmb_" + k, "      ↳ " + lab, wh, "dm_nc_read", 3, False, nc + [(B2, "in", [lab])])
    add("dm_nc_log", "memo: non-cold with a logistics exception", "NDR / repeat attempt - overlaps the rows above, not additive", "dm_nc", 1, False,
        nc + [(B3, "in", ["Logistics exception recorded"])])

    MQ = [(ISSUE, "in", ["Missing / short quantity"])]
    add("mq", "Missing / short quantity", "tickets", "raised", 0, True, MQ)
    add("mq_sku", "↳ SKU missing", "whole line / empty box / not received - the 2 rows add up to the total", "mq", 1, False, MQ + [(B1, "in", ["SKU missing"])])
    add("mq_item", "↳ item missing", "partial quantity (some units of the SKU sent) - single or multipack SKU", "mq", 1, False, MQ + [(B1, "in", ["Item missing"])])
    im = MQ + [(B1, "in", ["Item missing"])]
    add("mq_im_pack", "↳ pack qty confusion", "item missing: pack-vs-single confusion (owner bucket 1)", "mq_item", 2, False, im + [(B2, "in", ["Pack qty confusion"])])
    add("mq_im_pack_cust", "↳ customer end", "expected more than the invoice said - not provable from system data", "mq_im_pack", 3, False,
        im + [(B3, "in", ["Customer end (likely)"])])
    WHS = ["WH / system: inward unit mismatch", "WH / system: catalog / MDM pack definition", "WH / system: pack SKU, WH accepted short"]
    add("mq_im_pack_wh", "↳ WH / system issue", "inward, catalog or pack definition", "mq_im_pack", 3, False, im + [(B3, "in", WHS)])
    add("mq_im_pack_inw", "↳ inward unit mismatch", "GRN qty = pack size x PO qty (or reverse), dated on/before the order", "mq_im_pack_wh", 4, False, im + [(B3, "in", [WHS[0]])])
    add("mq_im_pack_cat", "↳ catalog / MDM pack definition", "name vs mapping conflict, MDM pack qty changed by the mapping, SKU missing from the mapping", "mq_im_pack_wh", 4, False, im + [(B3, "in", [WHS[1]])])
    add("mq_im_pack_acc", "↳ pack SKU, WH accepted short", "", "mq_im_pack_wh", 4, False, im + [(B3, "in", [WHS[2]])])
    add("mq_im_count", "↳ counting error", "item missing: count short at packing (owner bucket 2)", "mq_item", 2, False, im + [(B2, "in", ["Counting error"])])
    add("mq_im_count_conf", "↳ confirmed by WH", "WH admitted short qty", "mq_im_count", 3, False, im + [(B3, "in", ["Confirmed by WH"])])
    add("mq_im_count_elim", "↳ by elimination", "no pack flag, WH did not accept - default, not proof", "mq_im_count", 3, False, im + [(B3, "in", ["By elimination (WH did not accept)"])])
    add("mq_im_unid", "↳ SKU not identified", "no return line and no SKU in the ticket", "mq_item", 2, False, im + [(B2, "in", ["SKU not identified"])])
    add("mq_im_pend", "↳ tags pending", "new orders not yet covered by the pack-mapping / inward pull", "mq_item", 2, False, im + [(B2, "in", ["Tags pending"])])
    add("mq_text", "memo: classified from the ticket text", "no return item - overlaps the 2 rows above", "mq", 1, False, MQ + [(BASIS, "in", ["Ticket text"])])
    add("mq_default", "memo: default to item missing", "no return item and no detail in the ticket - overlaps the 2 rows above", "mq", 1, False,
        MQ + [(BASIS, "in", ["Default (no detail)"])])
    add("sw", "Order swap", "tickets", "raised", 0, True, [(ISSUE, "in", ["Order swap"])])
    add("mrp", "MRP / batch mismatch", "tickets (new sub-disposition)", "raised", 0, True, [(ISSUE, "in", ["MRP / batch mismatch"])])
    return _cascade(L)


def _cascade(L):
    """Owner rule: every deep dive sits directly BELOW its parent metric, indented one level per step
    down the tree - no exceptions. Rows are re-ordered depth-first (siblings keep their declared order),
    `indent` is derived from the parent chain (top-level metrics = 0) and the label prefix is derived from
    it too, so nothing depends on hand-typed spaces."""
    import re
    by_parent = {}
    for r in L:
        by_parent.setdefault(r["parent"], []).append(r)
    keys = {r["key"] for r in L}
    assert all(r["parent"] is None or r["parent"] in keys for r in L), "row with unknown parent"
    out = []

    def walk(parent, depth):
        for r in by_parent.get(parent, []):
            out.append(r)
            r["_depth"] = depth
            walk(r["key"], depth + 1)

    walk(None, 0)
    assert len(out) == len(L), "unreachable rows in layout"
    for r in out:
        d = r.pop("_depth") - 1          # 'raised' is the root (depth 0); its direct rows are top-level metrics
        d = max(d, 0)
        text = re.sub(r"^[\s\u21b3]+", "", r["label"])
        r["indent"] = d
        r["label"] = text if d == 0 else "\u21b3 " + text
    return out


def _match(row, col, where):
    for c, op, vals in where:
        v = row[col[c]]
        if (op == "in") != (v in vals):
            return False
    return True


def evaluate(export, layout, return_state=None, days=None):
    """export dict (rca_export.json) + layout -> rca_trend.json structure.
    return_state: None (All) or one of RET_STATES - the global "Return request" cut applied to every row."""
    col = {c: i for i, c in enumerate(export["columns"])}
    cutoff = export["t2_cap_date"]
    dcol = col["Created date"]
    rows = [r for r in export["rows"] if r[dcol] <= cutoff]
    if return_state:
        rows = [r for r in rows if r[col[RET]] == return_state]
    if not days:
        # calendar days (never just the days that have rows - a sparse view would make "last 30 days" cover more than 30 days),
        # trailing WINDOW_DAYS ending at the cutoff
        from datetime import date, timedelta
        last = date.fromisoformat(cutoff)
        first = max(date.fromisoformat(min(r[dcol] for r in rows)), last - timedelta(days=WINDOW_DAYS - 1)) if rows else last
        days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        rows = [r for r in rows if r[dcol] >= days[0]]
    # variants reuse All's day columns so the selector never shifts them
    by_day = {}
    for r in rows:
        by_day.setdefault(r[dcol], []).append(r)
    by_day = {d: by_day.get(d, []) for d in days}

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
        out.append({"key": it["key"], "label": it["label"], "sub": it["sub"] or None, "kind": "wfr_pto" if it["head"] else "plain", "indent": it["indent"],
                    "3mo": cell(it, days), "1mo": cell(it, days[-30:]), "2wk": cell(it, days[-14:]),
                    "daily": {d: cell(it, [d]) for d in days}})
    labels = {d: f"{int(d[8:10])} {MONTHS[int(d[5:7]) - 1]}" for d in days}
    held = sum(1 for r in export["rows"] if r[dcol] > cutoff and (not return_state or r[col[RET]] == return_state))
    return {"days": days, "day_labels": labels, "rows": out, "as_of": export["generated_at"][:10], "t2_cutoff": cutoff, "excluded_tickets": held}


def write_spec(path=HERE / "rca_view_spec.json", export=None):
    out = {"layout": build_layout(), "return_states": RET_STATES}
    if export:
        out.update({"t2_cap_date": export["t2_cap_date"], "generated_at": export["generated_at"]})
    Path(path).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
