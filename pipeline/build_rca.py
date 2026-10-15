"""
Builds pipeline/rca.json - the RCA layer for the dashboard's "6 - RCA" tab.

Two views per raised ticket:

1. INVESTIGATION FUNNEL (how the warehouse handled it). Owner-decided
   (2026-10-14): `Dependency` is NOT reliable as a funnel stage (agents remove
   it later), so the funnel is by OUTCOME of the Warehouse-team comment:
     Raised -> Accepted | Rejected | No decision | Not yet read
   and No decision is broken down, first match wins:
     footage_missing, batch_not_in_inventory (the "not from our inventory"
     claim), cx_image_unclear (WH said so, OR our own reading of every image
     on the return was unreadable), dependency_not_marked (Zoho Dependency
     is anything other than "Warehouse", incl. unfilled), return_not_received_at_wh,
     other_wh_note, no_wh_comment.
   "Not yet read" = no Warehouse-comment verdict cached yet; that is a
   coverage gap, deliberately NOT folded into No decision.

2. ISSUE RCA (why it happened) - deterministic ClickHouse checks from
   rca_expiry.json (expiry shelf life at delivery) and rca_binmap.json
   (same-bin / same-rack), written by build_rca_inputs.py. Every check keeps
   its evidence and a strength label; "undetermined" is a valid outcome.

T-2 CAP: same convention as the macro table / EOD tab - the cap date is the
IST date of data.json `generated_at` minus 2 days; newer tickets are flagged
`in_t2: false` and excluded from the funnel totals (WH has not had time to
comment). Day bucket is the UTC date of `created_time`, matching Tab 1.

Reconciliation (checked, printed, stored as `reconciles`): the investigation
leaves must sum to the dependency bucket, and the dependency buckets must sum
to raised. Never ships a funnel that drops a ticket silently.

People are never named as a cause; only order/ticket IDs, SKUs, bins.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wh_comment_classifier import investigation_subtype

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
IST = timezone(timedelta(hours=5, minutes=30))
T_MINUS_DAYS = 2


def load(name, default):
    p = RAW / name
    return json.loads(p.read_text()) if p.exists() else default


def investigation_state(check):
    """-> (state, subtype). state is one of: accepted | rejected |
    not_investigated | not_yet_checked."""
    if not check:
        return "not_yet_checked", None
    v = check.get("verdict")
    if v == "admitted":
        return "accepted", None
    if v == "denied":
        return "rejected", None
    if v == "no_wh_comment":
        return "not_investigated", "no_wh_comment"
    # unrecognized: WH commented but it is neither admission nor denial. The sub-reason is stored
    # at read time from every WH comment (`subtype`); fall back to the evidence text for old rows.
    return "not_investigated", check.get("subtype") or investigation_subtype(check.get("evidence")) or "other"


# DocPharma runs as warehouse_id 4 (verified on 7 DocPharma return orders, 2026-10-14).
DOCPHARMA_WAREHOUSE_ID = 4
COGS_THRESHOLD = 100
NO_DECISION_REASONS = ["footage_missing", "batch_not_in_inventory", "cx_image_unclear",
                       "dependency_not_marked", "docpharma", "cogs_lt_100", "agent_mistake",
                       "return_not_received_at_wh", "other_wh_note"]


def no_wh_comment_reason(dependency, meta):
    """Nobody from Warehouse commented. Owner rule: agents must not mark Warehouse
    dependency when (a) another dependency applies, (b) COGS < 100, or (c) it is a
    DocPharma order. If none of those hold, a Warehouse dependency was an agent mistake
    (the warehouse was asked to investigate something it should not have been).
    COGS = sum(allocated qty x zoho_inward_items.rate of the allocated batch) for the
    order; only trusted when every line has a rate, otherwise it is 'unknown'."""
    if dependency != "Warehouse":
        return "dependency_not_marked", None
    if dependency == "Doc Pharma" or (meta or {}).get("warehouse_id") == DOCPHARMA_WAREHOUSE_ID:
        return "docpharma", None
    m = meta or {}
    complete = bool(m.get("lines")) and m.get("lines_with_rate") == m.get("lines")
    known_ge = m.get("cogs") is not None and m["cogs"] >= COGS_THRESHOLD  # partial sum is a lower bound
    if complete and m["cogs"] < COGS_THRESHOLD:
        return "cogs_lt_100", None
    return "agent_mistake", (None if (complete or known_ge) else "cogs_unknown")


def image_status(order_id, images_by_order, category=None):
    """'legible' | 'unclear' | 'not_read' for the return images of an order.
    What must be legible depends on the complaint (owner rule): Wrong Medicines needs
    only the received SKU NAME (brand) - not batch/expiry, which are only a bonus from
    the back of the pack; Expiry needs the printed expiry or batch; anything else is
    legible if brand, batch or expiry is."""
    imgs = images_by_order.get(order_id)
    if not imgs:
        return "not_read"
    need = ("brand",) if category == "Wrong Medicines" else \
           ("expiry", "batch") if category == "Expiry Issue" else ("brand", "batch", "expiry")
    def ok(r):
        lg = r.get("legibility") or {}
        return any(lg.get(k) in ("high", "medium") for k in need)
    return "legible" if any(ok(r) for r in imgs) else "unclear"


CANCEL_CODES = {280, 231}   # marketplace_status_master: cancelledReturn, returnPickupCancelled


def return_state(resolution, order_id, ret_status, outcomes=None):
    """Where the return request stands (owner view, 2026-10-15), from the DTO return request of the order:
      not_raised        - no customer (DTO) return request (RTO / courier-only returns are not complaints)
      cancelled         - every request is cancelledReturn (280) or returnPickupCancelled (231)
      rejected          - the facility QC (250) rejected at least one return item
      accepted_refunded - facility QC done / refund approved (250, 245, 246, 247), nothing rejected
      in_progress       - requested, pickup / transit / validation not finished yet
    `outcomes` = rca_return_outcome_raw.json rows keyed by order_id (statuses, rejected item count)."""
    x = (outcomes or {}).get(order_id)
    if x is None:
        if resolution == "no_return_record":
            return "not_raised"
        codes = [c for c in ret_status.get(str(order_id), []) if c]
        if codes and all(c in CANCEL_CODES for c in codes):
            return "cancelled"
        return "in_progress"
    st = {c for c in x["st"] if c is not None}
    if st and st <= CANCEL_CODES:
        return "cancelled"
    if 250 in st and (x.get("rej") or 0) > 0:
        return "rejected"
    if st & {250, 245, 246, 247}:
        return "accepted_refunded"
    return "in_progress"


def decide(state, subtype, dependency, img_status, meta=None):
    """-> (decision, no_decision_reason)"""
    if state == "accepted":
        return "accepted", None
    if state == "rejected":
        return "rejected", None
    if state == "not_yet_checked":
        return "not_yet_read", None
    # state == not_investigated
    if subtype in ("footage_missing", "batch_not_in_inventory"):
        return "no_decision", subtype
    if subtype == "cx_image_unclear" or img_status == "unclear":
        return "no_decision", "cx_image_unclear"
    if dependency != "Warehouse":
        return "no_decision", "dependency_not_marked"
    if subtype == "return_not_received_at_wh":
        return "no_decision", subtype
    if subtype == "no_wh_comment":
        return ("no_decision",) + (no_wh_comment_reason(dependency, meta)[0],)
    return "no_decision", "other_wh_note"


def main():
    data = json.loads((HERE / "data.json").read_text())
    tickets = data["tickets"]
    deps = load("ticket_dependency.json", {})
    checks = load("wh_text_check.json", {})
    expiry = load("rca_expiry.json", {})
    binmap = load("rca_binmap.json", {})
    order_meta = load("rca_order_meta.json", {})
    wrongmed = load("rca_wrongmed.json", {})
    extra = load("rca_extra.json", {"tickets": {}, "summary": {}, "mrp_sample": []})
    manual_labels = load("rca_manual_labels.json", {})
    ret_status = load("rca_return_status.json", {})   # order_id -> distinct return_status codes (only orders with a cancel/multi/null state are listed)
    from image_reads import reads_by_order
    images_by_order = reads_by_order()
    outcomes = {int(r["order_id"]): r for r in (load("rca_return_outcome_raw.json", {}).get("result", {}).get("data") or [])}
    rs_override = load("rca_return_state_override.json", {})   # order -> why: RTO-only returns are not complaint requests

    gen = datetime.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cap = (gen.astimezone(IST) - timedelta(days=T_MINUS_DAYS)).date().isoformat()

    rows = []
    # One row per order, first ticket wins - identical to the dashboard's dedupeByOrder(), so every RCA
    # count reconciles with the Everything tab's "Total issues raised (unique per order)" tile.
    seen_orders, dup_dropped = set(), 0
    for t in tickets:
        if t["order_id"] in seen_orders:
            dup_dropped += 1
            continue
        seen_orders.add(t["order_id"])
        tid = t["ticket_id"]
        state, sub = investigation_state(checks.get(tid))
        dep_raw = deps.get(tid)
        dependency = dep_raw if dep_raw else "Not recorded"
        day = t["created_time"][:10]
        img = image_status(t["order_id"], images_by_order, t["category"])
        lab = manual_labels.get(str(t["order_id"])) or {}
        if lab.get("image_unreadable"):
            img = "unclear"
        meta = order_meta.get(str(t["order_id"]))
        decision, nd_reason = decide(state, sub, dependency, img, meta)
        agent_mistake_note = (no_wh_comment_reason(dependency, meta)[1]
                              if nd_reason == "agent_mistake" else None)
        rows.append({
            "ticket_id": tid,
            "order_id": t["order_id"],
            "date": day,
            "category": t["category"],
            "location": t["location"],
            "resolution": t["resolution"],
            "dependency": dependency,
            "decision": decision,
            "no_decision_reason": nd_reason,
            "return_state": ("not_raised" if str(t["order_id"]) in rs_override else
                             return_state(t["resolution"], t["order_id"], ret_status, outcomes)),
            "agent_mistake_note": agent_mistake_note,
            "extra": extra["tickets"].get(tid),
            "is_cold": t.get("is_cold") if "is_cold" in t else None,
            "wrong_med": wrongmed.get(str(t["order_id"])) if t["category"] == "Wrong Medicines" else None,
            "cogs": (order_meta.get(str(t["order_id"])) or {}).get("cogs"),
            "image_status": img,
            "images_read": len(images_by_order.get(t["order_id"], [])),
            "dependency_fetched": tid in deps,
            "state": state,
            "subtype": sub,
            "in_t2": day <= cap,
            "expiry": expiry.get(tid),
            "bin": binmap.get(tid),
        })

    # --- reconciliation over the T-2-eligible set ---
    elig = [r for r in rows if r["in_t2"]]
    top = Counter(r["decision"] for r in elig)
    nd = Counter(r["no_decision_reason"] for r in elig if r["decision"] == "no_decision")
    reconciles = (sum(top.values()) == len(elig) and sum(nd.values()) == top["no_decision"]
                  and all(k in NO_DECISION_REASONS for k in nd))

    out = {
        "generated_at": data["generated_at"],
        "t2_cap_date": cap,
        "excluded_tickets": len(rows) - len(elig),
        "raised_in_scope": len(elig),
        "dependency_fetched": sum(1 for r in rows if r["dependency_fetched"]),
        "reconciles": reconciles,
        "no_decision_reasons": NO_DECISION_REASONS,
        "duplicate_tickets_dropped": dup_dropped,
        "extra_summary": extra.get("summary"),
        "mrp_sample": extra.get("mrp_sample"),
        "damaged_noncold": load("rca_damaged_noncold.json", None),
        "mrp_gaps": extra.get("mrp_gaps"),
        "rows": rows,
    }
    (HERE / "rca.json").write_text(json.dumps(out))
    print(f"rca.json: {len(rows)} tickets, {len(elig)} in T-2 scope (cap {cap}), reconciles={reconciles}")
    print("  " + ", ".join(f"{k}={v}" for k, v in top.most_common()))
    print("  no decision: " + ", ".join(f"{k}={v}" for k, v in nd.most_common()))
    rs = Counter(r["return_state"] for r in elig if r["decision"] == "no_decision")
    print("  no decision by return state: " + ", ".join(f"{k}={v}" for k, v in rs.most_common()))
    if not reconciles:
        raise SystemExit("RCA funnel does not reconcile - not shipping")


if __name__ == "__main__":
    main()
