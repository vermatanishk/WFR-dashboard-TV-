"""
Complaint baseline = UNION of the two places a customer complaint can show up (owner, 2026-10-25):
  1. ClickHouse return requests (type DTO) - the master list of everything customers raise in the app / with an agent;
  2. Zoho Desk tickets (every disposition pulled by pull_complaint_tickets.py) - the active investigation.
The old WFR base was Zoho tickets only, so any complaint nobody ticketed was invisible. Here a complaint is
(order, complaint type) and we then ask: did it get a Zoho ticket, did the Warehouse get asked, and what was it about.

Complaint types (MECE): Wrong medicine | Missing / short qty | Expiry | Damage | Order swap | MRP / batch mismatch.
Return reasons that are not mis-shipments (No longer needed, Prescription changed, Allergic reaction, Substitutes not
needed, Duplicate order ...) are NOT complaints and never enter the baseline (they are only counted in the sanity block).

Inputs (zoho_raw90/):
  cmp_returns_c0..c3.json  ClickHouse, one row per (order, drug_code) with the FINAL reason (latest request wins:
                           a customer first picks "Received Wrong Medicines" and re-submits the same item as "No longer
                           needed" a minute later - the first request is a dead draft). Query shape below.
  cmp_zoho_tickets.json    pull_complaint_tickets.py (all dispositions, IDs only)
  wh_text_check.json       Warehouse comment verdicts per ticket (recheck_wh_comments.py --extra cmp_tickets_to_read.json)
  damage30_image_buckets.json / damage30_orders.json   hand-read photo buckets for damage (see damage_images.py)

ClickHouse query (per 15-day chunk, saved by the session as cmp_returns_cN.json; DTO only, drop _peerdb_is_deleted):
  WITH rr AS (SELECT * FROM marketplace_return_request WHERE _peerdb_is_deleted=0 AND type='DTO' AND created_at >= A AND created_at < B
              ORDER BY _peerdb_version DESC LIMIT 1 BY id),
       ri AS (SELECT * FROM marketplace_return_items WHERE _peerdb_is_deleted=0 ORDER BY _peerdb_version DESC LIMIT 1 BY id),
       x AS (SELECT rr.order_id order_id, ri.drug_code drug_code, min(rr.created_at) created,
                    argMax(ri.reason, rr.created_at) reason, argMax(rr.return_status, rr.created_at) status,
                    argMax(toUInt8(ri.rejected_for_damage OR ri.rejected_for_batch_mismatch OR ri.rejected_for_others), rr.created_at) rej,
                    count() n_req FROM rr JOIN ri ON ri.return_request_id=rr.id GROUP BY rr.order_id, ri.drug_code), ...
  + LEFT JOIN mdm_master_drug_data (cold_storage) and marketplace_orders (warehouse_id), joined on order_id.

Output: complaints_export.json  {columns, rows, t2_cap_date, generated_at, window_start, notes}, one row per complaint,
        plus a sanity block printed (and asserted) here.
Run: python3 pipeline/build_complaints.py
"""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
IST = timezone(timedelta(hours=5, minutes=30))

WM, MQ, EXP, DMG, SWP, MRP = "Wrong medicine", "Missing / short qty", "Expiry", "Damage", "Order swap", "MRP / batch mismatch"
TYPES = [WM, MQ, EXP, DMG, SWP, MRP]
DAMAGE_START = "2026-09-20"              # photo-read scope of the Order damage tab (owner: last 30 days)
WFR_TYPES = [WM, MQ, EXP, MRP]            # the WFR funnel tab; Damage and Swap have their own tabs
CANCEL_CODES = {280, 231}                 # cancelledReturn, returnPickupCancelled (marketplace_status_master)
REFUND_CODES = {250, 245, 246, 247}       # facility QC done / refund approved

R_ACC, R_CAN, R_REJ, R_PROG, R_NONE = ("Raised - Accepted & refunded", "Raised - Cancelled", "Raised - Rejected",
                                       "Raised - In progress", "Not raised")

COLUMNS = ["Order ID", "Created date", "Complaint type", "Source", "Return request", "Return reason (final)", "In scope",
           "Ticket relation", "Ticket raised", "Ticket ID", "Ticket sub-disposition", "WH input", "Damage type", "Cold item",
           "Photo bucket", "Warehouse",
           "RCA read", "RCA investigation", "RCA no-decision reason", "RCA bucket 1", "RCA bucket 2", "RCA bucket 3", "RCA evidence basis"]

T_MATCH, T_OTHER, T_NONCMP, T_NONE = ("Filed under this complaint type", "Filed under another complaint type",
                                      "Filed as non-complaint (e.g. No longer needed)", "No ticket")
SRC_BOTH, SRC_RET, SRC_TKT = "Return request + ticket", "Return request only", "Zoho ticket only"
WH_ACC, WH_DEN, WH_OTH, WH_NONE, WH_DUE, WH_GAP, WH_NA = ("WH accepted", "WH denied", "WH other note", "No WH comment",
                                                          "Not due yet (T-2)", "Verdict not read (gap)", "No ticket")
DMG_TEMP, DMG_PHYS = "Temperature complaint (cold chain)", "Physical damage"
P_OTHER = "Return filed under another reason (photo not checked)"
P_NA, P_UNREAD, P_NOFILE, P_TEMP = ("Photo not available (no return request)", "Photo not read yet", "No photo on file",
                                    "Not photo-read (temperature complaint)")


def parse_order_id(raw):
    """Same rule as build_full_dataset.parse_order_id (not imported: that module rebuilds data.json on import).
    Placeholder text, multi-order text and phone-number-sized values -> None; never guesses between candidates."""
    if not raw:
        return None
    s = str(raw).strip().rstrip(".")
    if not s or " " in s or not s.lstrip("+-").isdigit():
        return None
    n = int(s)
    return n if 10**5 <= n <= 10**9 else None


def reason_type(reason):
    """Final return reason (free text, many typos) -> complaint type, or None = not a mis-shipment complaint."""
    s = re.sub(r"\s+", " ", (reason or "").strip().lower())
    if not s:
        return None
    if "swap" in s or "switch" in s:
        return SWP
    if "mrp" in s or "batch mismatch" in s:
        return MRP
    if "wrong medic" in s or "wrong item" in s:
        return WM
    if "incomplete order" in s or "missing" in s or "less quantity" in s or "short qty" in s:
        return MQ
    if "expir" in s:
        return EXP
    if "cold storage" in s or "damag" in s or "defective" in s or "leak" in s or "spill" in s or "broken" in s:
        return DMG
    return None


# Zoho sub-disposition -> complaint type. Mapped ones reuse the dashboard's CATEGORY_MAP; the extra damage sub-dispositions
# below are the ones the dashboard never pulled (found 2026-10-20: 118 of 553 damage orders had such a ticket).
from category_mapping import CATEGORY_MAP

_CAT_TO_TYPE = {"Missing/Wrong Qty": MQ, "Wrong Medicines": WM, "Expiry Issue": EXP, "Damaged/Defective": DMG,
                "Switch Orders": SWP, "MRP/Batch Mismatch": MRP}
SUB_EXTRA = {"cold storage item delivered warm": DMG, "damaged packaging or container": DMG, "order swapped": SWP}


def sub_type(sub):
    k = (sub or "").strip().lower()
    if k in SUB_EXTRA:
        return SUB_EXTRA[k]
    cat = CATEGORY_MAP.get(k)
    return _CAT_TO_TYPE.get(cat)


def load_returns():
    items = {}
    for p in sorted(RAW.glob("cmp_returns_c*.json")):
        for r in json.loads(p.read_text())["result"]["data"]:
            k = (r["order_id"], r["drug_code"])
            if k in items:                                  # item straddles a chunk boundary: the later request is the final one
                old = items[k]
                new, prev = (r, old) if r["created"] >= old["created"] else (old, r)
                r = {**new, "created": min(old["created"], r["created"]), "n_req": old["n_req"] + r["n_req"]}
            items[k] = r
    return list(items.values())


def ret_state(lines):
    """Outcome of the return request(s) behind a complaint: every item cancelled -> Cancelled; any item QC-rejected -> Rejected;
    any item refunded -> Accepted & refunded; otherwise still in progress (status None = request not yet processed)."""
    if all(x["status"] in CANCEL_CODES for x in lines):
        return R_CAN
    if any(x["status"] == 250 and x["rej"] for x in lines):
        return R_REJ
    if any(x["status"] in REFUND_CODES for x in lines):
        return R_ACC
    return R_PROG


def main():
    gen = datetime.now(timezone.utc)
    cap = (gen.astimezone(IST) - timedelta(days=2)).date().isoformat()          # T-2 for Warehouse comments
    store = json.loads((RAW / "cmp_zoho_tickets.json").read_text())
    tickets = [t for day in store["days"].values() for t in day]
    wh_cache = json.loads((RAW / "wh_text_check.json").read_text())

    # ---------- return side: (order, type) -> lines
    items = load_returns()
    win_start = min(x["created"][:10] for x in items)
    ret = defaultdict(list)
    any_lines = defaultdict(list)          # every DTO return line of the order, any reason (for ticket-only complaints)
    skipped = Counter()
    for x in items:
        any_lines[x["order_id"]].append(x)
        t = reason_type(x["reason"])
        if t is None:
            skipped[(x["reason"] or "").strip()] += 1
            continue
        ret[(x["order_id"], t)].append(x)

    # ---------- zoho side
    by_order = defaultdict(list)
    unlinked = Counter()
    for t in tickets:
        oid = parse_order_id(t["order_raw"])
        if oid is None:
            unlinked["no/ambiguous order id"] += 1
            continue
        by_order[oid].append({**t, "order_id": oid, "type": sub_type(t["sub_disposition"])})
    for v in by_order.values():
        v.sort(key=lambda t: t["created_time"])

    # warehouse id -> name, learnt from the dashboard's own order->location join (majority vote)
    votes = defaultdict(Counter)
    whid = {}
    for x in items:
        whid[x["order_id"]] = x["wh"]
    for tk in json.loads((HERE / "data.json").read_text())["tickets"]:
        w = whid.get(tk["order_id"])
        if w is not None and tk["location"] != "Unknown":
            votes[w][tk["location"]] += 1
    wh_name = {w: c.most_common(1)[0][0] for w, c in votes.items()}

    photo = {}
    bk = json.loads((RAW / "damage30_image_buckets.json").read_text())["order_bucket"]
    universe = {x["order"]: x["cat"] for x in json.loads((RAW / "damage30_orders.json").read_text())}
    from damaged_buckets import BUCKETS
    code_label = dict(zip("PCOLQDNX", [b[1] for b in BUCKETS]))
    # damaged_buckets order: primary, carton, outer, leak, quality, label, none, not-relevant  == P C O L Q D N X
    for o, c in bk.items():
        photo[int(o)] = code_label[c]

    # root-cause columns from the RCA export (one row per order, issue = ticket's category); joined on (order, complaint type)
    rca_issue = {"Missing / short quantity": MQ, "Wrong medicine": WM, "Expiry": EXP, "Damaged": DMG}
    rca_exp = json.loads((HERE / "rca_export.json").read_text())
    RC = {c: i for i, c in enumerate(rca_exp["columns"])}
    rca = {}
    for r in rca_exp["rows"]:
        t = rca_issue.get(r[RC["Issue"]])
        if t:
            rca[(r[RC["Order ID"]], t)] = r
    rca_cols = ["Investigation bucket 1", "Investigation bucket 2", "Raised bucket 1", "Raised bucket 2", "Raised bucket 3", "Evidence basis"]
    rank = {"admitted": 3, "denied": 2, "unrecognized": 1, "no_wh_comment": 0}

    def day_shift(d, n):
        return (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=n)).strftime("%Y-%m-%d")

    def make_row(oid, typ, lines, rel, chosen):
        """One complaint row. lines = return lines of THIS complaint type; chosen = the investigation ticket(s) attached."""
        raised = "Yes" if rel in (T_MATCH, T_OTHER) else "No"
        # complaint date: the day the customer raised it (return request), else the ticket's day
        dates = ([min(x["created"] for x in lines)[:10]] if lines else []) + ([chosen[0]["created_time"][:10]] if raised == "Yes" else [])
        created = min(dates)
        # Return request state: the complaint's own lines; for a ticket-only complaint the order's other return lines
        # (the customer may have returned the item under a non-complaint reason such as "No longer needed")
        other = any_lines.get(oid, []) if not lines else []
        state = ret_state(lines) if lines else ret_state(other) if other else R_NONE
        src = SRC_BOTH if lines and raised == "Yes" else SRC_RET if lines else SRC_TKT
        in_scope = "No" if state in (R_CAN, R_REJ) else "Yes"
        wh = WH_NA
        if raised == "Yes":                                              # best verdict across the attached tickets
            best = None
            for t in chosen:
                v = (wh_cache.get(t["ticket_id"]) or {}).get("verdict")
                if v is not None and (best is None or rank.get(v, 0) > rank.get(best, 0)):
                    best = v
            if chosen[0]["created_time"][:10] > cap:
                wh = WH_DUE
            elif best is None:
                wh = WH_GAP
            else:
                wh = {"admitted": WH_ACC, "denied": WH_DEN, "unrecognized": WH_OTH, "no_wh_comment": WH_NONE}[best]
        reasons = [x["reason"] for x in (lines or other)]
        reason = Counter(reasons).most_common(1)[0][0].strip() if reasons else ""
        dmg_type, pb = "", ""
        if typ == DMG:
            temp = any("cold storage" in (x["reason"] or "").lower() for x in lines) or \
                any((t["sub_disposition"] or "").strip().lower() == "cold storage item delivered warm" for t in chosen)
            dmg_type = DMG_TEMP if temp else DMG_PHYS
            if temp:
                pb = P_TEMP
            elif not lines:
                pb = P_NA if state == R_NONE else P_OTHER      # the customer did return it, just under another reason
            elif oid in photo:
                pb = photo[oid]
            elif universe.get(oid) == "No photo on file":
                pb = P_NOFILE
            else:
                pb = P_UNREAD
        ws = whid.get(oid)
        rr = rca.get((oid, typ)) if raised == "Yes" else None
        rca_vals = ["Yes"] + [rr[RC[c]] or "" for c in rca_cols] if rr else ["No"] + [""] * len(rca_cols)
        return [oid, created, typ, src, state, reason, in_scope, rel, raised,
                chosen[0]["ticket_id"] if chosen else "", (chosen[0]["sub_disposition"] or "") if chosen else "",
                wh, dmg_type, "Yes" if any(x["cold"] for x in lines) else "No", pb,
                wh_name.get(ws, f"WH {ws}" if ws is not None else "Unknown")] + rca_vals

    # One real complaint must be ONE row: a ticket explains at most one return complaint, and a ticket that explains a
    # return complaint never also becomes a "ticket only" complaint.
    rows = []
    orphans, accounted = [], set()
    orders = {o for (o, _) in ret} | set(by_order)
    for oid in sorted(orders):
        tk_all = by_order.get(oid, [])
        typed = [t for t in tk_all if t["type"]]
        noncmp = [t for t in tk_all if not t["type"] and t["disposition"] == "Return and Pickup"]
        mine = {typ: ls for (o, typ), ls in ret.items() if o == oid}
        claimed, attach = set(), {}

        def near(ts, lines):
            c0 = min(x["created"] for x in lines)[:10]
            lo, hi = day_shift(c0, -30), day_shift(c0, 60)
            return [t for t in ts if lo <= t["created_time"][:10] <= hi]

        for typ, lines in mine.items():                                  # pass 1: exact complaint type
            m = near([t for t in typed if t["type"] == typ], lines)
            if m:
                attach[typ] = (T_MATCH, m)
                claimed |= {t["ticket_id"] for t in m}
        for typ, lines in mine.items():                                  # pass 2: agent filed it under another type
            if typ in attach:
                continue
            m = near([t for t in typed if t["ticket_id"] not in claimed], lines)
            if m:
                attach[typ] = (T_OTHER, m[:1])
                claimed.add(m[0]["ticket_id"])
        for typ, lines in mine.items():
            if typ not in attach:
                m = near(noncmp, lines)
                attach[typ] = (T_NONCMP, m) if m else (T_NONE, [])
            rows.append(make_row(oid, typ, lines, *attach[typ]))
        left = defaultdict(list)                                         # pass 3: tickets nobody explained -> ticket-only
        for t in typed:
            if t["ticket_id"] not in claimed:
                left[t["type"]].append(t)
        for typ, ts in left.items():
            if typ in mine:                                              # same-type return exists but ticket is outside its window
                orphans.extend(t["ticket_id"] for t in ts)
                continue
            rows.append(make_row(oid, typ, [], T_MATCH, ts))
            claimed |= {t["ticket_id"] for t in ts}
        accounted |= claimed

    # window: complaints raised from the first fully pulled return day; drop partial first day if needed
    end_day = max(x["created"][:10] for x in items)                      # last day the return pull covers completely
    rows = [r for r in rows if win_start <= r[1] <= end_day]
    rows.sort(key=lambda r: (r[1], r[0], r[2]))
    latest = max(r[1] for r in rows)
    in_win = [t for t in tickets if (t["created_time"][:10] >= win_start) and sub_type(t["sub_disposition"]) and parse_order_id(t["order_raw"]) is not None]
    unaccounted = [t["ticket_id"] for t in in_win if t["ticket_id"] not in accounted]
    out = {"columns": COLUMNS, "rows": rows, "t2_cap_date": latest, "wh_t2_cap": cap, "window_start": win_start,
           "generated_at": gen.strftime("%Y-%m-%dT%H:%M:%SZ"), "zoho_pulled_at": store.get("pulled_at"),
           "notes": {"unlinked_tickets": dict(unlinked), "skipped_reasons_top": skipped.most_common(40)}}
    (HERE / "complaints_export.json").write_text(json.dumps(out, separators=(",", ":")))
    base_orders = {r[0] for r in rows}
    toread = [{"ticket_id": t["ticket_id"], "order_id": t["order_id"], "created_time": t["created_time"]}
              for o in base_orders for t in by_order.get(o, []) if t["type"]]
    (RAW / "cmp_tickets_to_read.json").write_text(json.dumps(toread))
    unl = [t for t in tickets if parse_order_id(t["order_raw"]) is None and (sub_type(t["sub_disposition"]) or t["disposition"] == "Return and Pickup")]
    out["notes"]["unaccounted_ticket_ids"] = unaccounted
    out["notes"]["unlinked_complaint_tickets"] = len(unl)
    out["notes"]["unlinked_complaint_ticket_ids"] = [t["ticket_id"] for t in unl][:200]
    (HERE / "complaints_export.json").write_text(json.dumps(out, separators=(",", ":")))
    tab_exports(out)
    sanity(out, items, tickets, skipped)
    print(f"tickets for Warehouse-comment read (baseline orders, complaint types): {len(toread)} -> zoho_raw90/cmp_tickets_to_read.json")
    print(f"complaint-type tickets with no usable order id (cannot be joined): {len(unl)}")
    print(f"complaint-type tickets in window not attached to any complaint row: {len(unaccounted)} {unaccounted[:8]}")


def tab_exports(out):
    """Per-tab slices with the same schema (the Google Sheet reads one raw tab per view)."""
    C = {c: i for i, c in enumerate(out["columns"])}
    base = {k: out[k] for k in ("columns", "t2_cap_date", "wh_t2_cap", "generated_at", "zoho_pulled_at", "notes")}
    wfr = [r for r in out["rows"] if r[C["Complaint type"]] in WFR_TYPES]
    dmg = [r for r in out["rows"] if r[C["Complaint type"]] == DMG and r[C["Created date"]] >= DAMAGE_START]
    swp = [r for r in out["rows"] if r[C["Complaint type"]] == SWP]
    for name, rows in (("wfr", wfr), ("damage", dmg), ("swap_baseline", swp)):
        (HERE / f"cmp_{name}_export.json").write_text(json.dumps({**base, "window_start": min(r[1] for r in rows), "rows": rows}, separators=(",", ":")))


def sanity(out, items, tickets, skipped):
    """Hard checks - a refresh must not ship if any of these fail (also re-checked independently by test_complaints.py)."""
    rows, C = out["rows"], {c: i for i, c in enumerate(out["columns"])}
    n = len(rows)
    key = Counter((r[0], r[2]) for r in rows)
    assert all(v == 1 for v in key.values()), "duplicate (order, type) complaint rows"
    assert sum(Counter(r[C["Source"]] for r in rows).values()) == n
    for r in rows:
        assert r[C["Source"]] != SRC_TKT or r[C["Ticket raised"]] == "Yes", r
        assert r[C["Source"]] == SRC_TKT or r[C["Return request"]] != R_NONE, r
        assert (r[C["In scope"]] == "No") == (r[C["Return request"]] in (R_CAN, R_REJ)), r
        assert r[C["Ticket raised"]] == ("Yes" if r[C["Ticket relation"]] in (T_MATCH, T_OTHER) else "No"), r
        assert (r[C["WH input"]] == WH_NA) == (r[C["Ticket raised"]] == "No"), r
    print(f"\nbaseline window {out['window_start']} .. {out['t2_cap_date']}   WH T-2 cap {out['wh_t2_cap']}")
    print(f"complaints (order x type): {n}   unique orders: {len({r[0] for r in rows})}")
    for t in TYPES:
        sub = [r for r in rows if r[C['Complaint type']] == t]
        ins = [r for r in sub if r[C['In scope']] == 'Yes']
        tk = [r for r in ins if r[C['Ticket raised']] == 'Yes']
        print(f"  {t:22s} all {len(sub):5d} | in scope {len(ins):5d} | ticket raised {len(tk):5d} ({100*len(tk)/max(len(ins),1):.0f}%)")
    print("source:", dict(Counter(r[C['Source']] for r in rows)))
    print("WH input (ticketed, in scope):", dict(Counter(r[C['WH input']] for r in rows if r[C['Ticket raised']] == 'Yes' and r[C['In scope']] == 'Yes')))
    gap = sum(1 for r in rows if r[C['WH input']] == WH_GAP)
    print(f"WH verdict gaps (ticket older than T-2, verdict not cached): {gap}")
    print("return reasons treated as NOT a complaint:", skipped.most_common(12))
    print("zoho tickets pulled:", len(tickets), "| without a usable order id:", out["notes"]["unlinked_tickets"])


if __name__ == "__main__":
    main()
