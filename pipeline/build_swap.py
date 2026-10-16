"""
Order-swap layer (separate Google-Sheet tab "Order Swap"; the original tabs are untouched).

Why separate: agents filed swaps as Wrong Medicine / Wrong item Delivered until the "Order Swap" sub-disposition
existed, so the swap population is found by a TEXT scan (pull_swap_tickets.py) and measured here on its own.

Case = one swap PAIR (earliest ticket of either order is the case's ticket, "first ticket wins") or, when no second
order can be established, one unpaired order ("Pair not identified"). Total cases = pairs + unpaired orders.

Pair evidence: ticket text naming the other order, the owner-confirmed pairs in zoho_raw90/swap_pairs_seed.json
(playbook 16 Oct 2026), and - ONLY for cases still unpaired - the order id printed on the invoice / courier label in the
complainant's own return images (read by the session with vision; `image_pairs` in the seed; images stay out of git,
unreadable ones are left as Pair not identified). ClickHouse inputs saved from the MCP: swap_orders.json (warehouse, pincode, courier),
swap_status_raw.txt (invoice / carrier-pickup / manifest agent + time, delivered time), swap_return_status.json.

Swap MECE (owner rule, 2026-10-16) - decided per pair, first match wins:
  1. same delivery pincode                                         -> Logistics issue / Same pincode delivery
  2. same warehouse AND warehouse-side link (needs a shared handler):
       manifests <= 60 s apart                                     -> WH issue / Manifested too closely
       shared packing handler (invoice or carrier-pickup <= 10 min apart), manifests far apart
                                                                   -> WH issue / Proximity in packing, separate manifestation
       any other shared handler at any stage                       -> WH issue / Other
  3. not attributable to the warehouse, both delivered the same day-> Logistics issue / Same day diff pincode delivery
  3b. box addressed to the complainant but another order's bill/items inside (ticket text or photo, `label_mismatch` in
      the seed; same warehouse)                                    -> WH issue / Other   [checked right after rule 1]
  3c. same warehouse, pincodes in different 2-digit regions (whole-parcel courier mix-up implausible) -> WH issue / Other (inferred)
  4. anything else                                                 -> Unclassified (no WH link, not same-day delivery)
Logistics is therefore only "same pincode" or "error not attributable to the warehouse" - courier match is NOT a rule,
it is kept as a column. Handlers are never exported (public repo): only the derived bucket.

Run: python3 pipeline/build_swap.py   -> swap_export.json (+ prints a summary)
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from build_rca import decide, investigation_state, return_state
from build_rca_export import COLUMNS, DECISION, ND, RET

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
WH = {1: "Bengaluru", 2: "Delhi", 3: "Mumbai", 4: "DocPharma", 5: "Lucknow", 6: "Kolkata", 7: "Mother Warehouse", 8: "Patna", 9: "Hyderabad", 10: "Guwahati"}
STRONG_WORDS = ("swap", "swipe", "another cx", "other cx", "another customer", "other customer", "different order", "someone else", "any one else", "other person", "mixed up", "label")
NOT_SWAP_DISPOSITIONS = {"Unprofessional behavior by delivery executive", "Account deletion request", "Refund not credited to account",
                         "Incorrect amount refunded", "Delayed or likely to be delayed", "Wrong item ordered"}
WINDOW_DAYS = 60


def load(n, default=None):
    p = RAW / n
    return json.loads(p.read_text()) if p.exists() else default


def parse_status():
    out = {}
    for ln in (RAW / "swap_status_raw.txt").read_text().splitlines():
        o, *rest = ln.split("|", 1)
        st = {}
        for part in rest[0].split(";"):
            stage, user, ts = part.split("|")
            st[stage] = (user, datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        out[int(o)] = st
    return out


def select_tickets():
    """-> ({ticket_id: ticket}, pairs[list of sorted order pairs])"""
    seed = load("swap_pairs_seed.json")
    excl = set(seed["exclude_orders"])
    tk = [t for t in load("swap_tickets.json")["tickets"] if not t["noise"]]
    pairs = {frozenset(p) for p in seed["pairs"]}
    keep = {}
    for t in tk:
        sd = t["order_swap_disposition"]
        strong = any(any(w in s for w in STRONG_WORDS) for s in t["signals"])
        if not (sd or strong):
            continue
        if not sd and t["sub_disposition"] in NOT_SWAP_DISPOSITIONS:
            continue
        orders = [x.strip() for x in re.split(r"[,\s]+", t["order_id"]) if x.strip().isdigit()]
        if not orders or any(int(o) in excl for o in orders):
            continue
        if len(orders) == 2:
            pairs.add(frozenset(int(o) for o in orders))
        for o in t["other_orders"]:
            if len(orders) == 1 and o != orders[0] and (sd or strong):
                pairs.add(frozenset((int(orders[0]), int(o))))
        t = dict(t, order_id=int(orders[0]))
        keep[t["ticket_id"]] = t
    pairs = [sorted(p) for p in pairs if len(p) == 2 and not (set(p) & excl)]
    return keep, pairs


def classify_pair(a, b, orders, status, label_mismatch=()):
    oa, ob = orders[str(a)], orders[str(b)]
    sa, sb = status.get(a, {}), status.get(b, {})
    courier = "Same" if oa["courier"] and oa["courier"] == ob["courier"] else ("Different" if oa["courier"] and ob["courier"] else "Unknown")
    if oa["pin"] and oa["pin"] == ob["pin"]:
        return "Logistics issue", "Same pincode delivery", "Same delivery pincode", courier
    if a in label_mismatch or b in label_mismatch:
        return ("WH issue", "Other", "Box addressed to one customer, another order's bill / items inside - label and contents separated at packing (ticket text / photo)", courier) if oa["wh"] == ob["wh"] else \
               ("Unclassified", "", "Label / contents mismatch reported, but the two orders ship from different warehouses", courier)
    if oa["wh"] == ob["wh"]:
        def t(s, k):
            return s[k][1] if k in s else None

        def u(s, k):
            return s[k][0] if k in s else None

        def gap(k):
            x, y = t(sa, k), t(sb, k)
            return abs((x - y).total_seconds()) if x and y else None
        shared = {k: (u(sa, k) is not None and u(sa, k) == u(sb, k) and u(sa, k) != "SYS") for k in ("INVOICE_GENERATED", "CARRIER_PICKUP_PENDING", "MANIFESTED")}
        gm = gap("MANIFESTED")
        if shared["MANIFESTED"] and gm is not None and gm <= 60:
            return "WH issue", "Manifested too closely", f"Same handler manifested both parcels {gm:.1f}s apart", courier
        close = [k for k in ("INVOICE_GENERATED", "CARRIER_PICKUP_PENDING") if shared[k] and gap(k) is not None and gap(k) <= 600]
        if close:
            return "WH issue", "Proximity in packing, separate manifestation", "Same handler at packing stage within 10 min; manifests far apart", courier
        if any(shared.values()):
            return "WH issue", "Other", "Shared handler at " + "/".join(k.lower() for k, v in shared.items() if v) + ", not close in time", courier
    da, db = t_del(sa), t_del(sb)
    if da and db and da == db:
        return "Logistics issue", "Same day diff pincode delivery", "No warehouse link; both delivered on the same day, different pincodes", courier
    if oa["wh"] == ob["wh"] and oa["pin"][:2] != ob["pin"][:2]:
        return "WH issue", "Other", "Same warehouse, delivery pincodes in different regions and the customer holds the other order's invoice: a whole-parcel courier mix-up is implausible, so contents were crossed before sealing (inferred)", courier
    return "Unclassified", "", "No warehouse link and not same-day delivery (or delivery not recorded)", courier


def t_del(s):
    return s["DELIVERED"][1].date() if "DELIVERED" in s else None


def main():
    tickets, pairs = select_tickets()
    orders, status = load("swap_orders.json"), parse_status()
    rstat = load("swap_return_status.json")
    lm = set(load("swap_pairs_seed.json").get("label_mismatch", {}).get("orders", []))
    checks, deps = load("wh_text_check.json"), load("ticket_dependency.json", {})
    rca = load("../rca.json") if False else json.loads((HERE / "rca.json").read_text())
    cap, gen = rca["t2_cap_date"], rca["generated_at"]
    start = (datetime.strptime(gen[:10], "%Y-%m-%d") - timedelta(days=WINDOW_DAYS)).date().isoformat()
    by_order = {}
    for t in sorted(tickets.values(), key=lambda x: x["created_time"]):
        by_order.setdefault(t["order_id"], []).append(t)
    pair_of = {}
    for a, b in pairs:
        pair_of.setdefault(a, []).append((a, b))
        pair_of.setdefault(b, []).append((a, b))
    cases, used, used_tickets = [], set(), set()
    img = load("swap_pairs_seed.json")["image_pairs"]["pairs"]
    img_basis = {}
    # one case per pair (earliest unused ticket of either order); a ticket anchors at most one case
    for a, b in sorted(pairs):
        ts = [t for t in by_order.get(a, []) + by_order.get(b, []) if t["ticket_id"] not in used_tickets]
        if not ts:
            continue
        first = min(ts, key=lambda x: x["created_time"])
        used |= {a, b}
        used_tickets.add(first["ticket_id"])
        cases.append((first, b if first["order_id"] == a else a, "Ticket text / owner-confirmed pair"))
    # pairs read from the complainant's return images: the complaint order's own ticket anchors the case; a mutual
    # swap (both customers complained) is one case
    done = set()
    for a, b in img:
        key = frozenset((a, b))
        ts = [t for t in by_order.get(a, []) if t["ticket_id"] not in used_tickets]
        if key in done or not ts:
            continue
        done.add(key)
        first = ts[0]
        if b in by_order:      # partner also complained: consume its first ticket as the same swap
            used_tickets.add(by_order[b][0]["ticket_id"])
        used |= {a, b}
        used_tickets.add(first["ticket_id"])
        cases.append((first, b, "Return image: invoice / label shows order " + str(b)))
    for o, ts in by_order.items():
        if o in used:
            continue
        cases.append((ts[0], None, ""))
    rows, stats = [], {}
    for t, partner, how in sorted(cases, key=lambda c: c[0]["created_time"]):
        if t["created"] < start:
            continue
        o = t["order_id"]
        meta = orders.get(str(o))
        if meta is None:
            print("no order facts for", o)
            continue
        if partner:
            b1, b2, basis, courier = classify_pair(o, partner, orders, status, lm)
            conf = "Likely"
            if how.startswith("Return image"):
                basis = how + "; " + basis
        else:
            b1, b2, basis, courier, conf = "Pair not identified", "", "Ticket names no second order", "Unknown", "Default"
        state, sub = investigation_state(checks.get(t["ticket_id"]))
        dep = deps.get(t["ticket_id"]) or t["dependency"] or "Not recorded"
        decision, reason = decide(state, sub, dep if dep != "Not recorded" else None, "not_read", {"warehouse_id": meta["wh"]})
        sts = rstat.get(str(o))
        if sts is None:
            rs = "not_raised"
        else:
            codes = [c for c in sts if c]
            rs = "cancelled" if codes and all(c in (280, 231) for c in codes) else \
                 "accepted_refunded" if 250 in codes else "in_progress"
        rows.append([o, t["ticket_id"], t["created"], WH.get(meta["wh"], str(meta["wh"])), "Order swap",
                     DECISION.get(decision, decision), ND.get(reason, "") if decision == "no_decision" else "",
                     RET[rs], dep, b1, b2, str(partner or ""), basis, conf, courier,
                     "Yes" if t["created"] <= cap else "No (held back, WH not yet commented)"])
    cols = COLUMNS[:9] + ["Swap bucket 1", "Swap bucket 2", "Pair order", "Evidence basis", "Confidence", "Courier match", "In T-2 scope"]
    out = {"generated_at": gen, "t2_cap_date": cap, "columns": cols, "rows": rows,
           "note": "One row per swap CASE (a pair counts once; unpaired orders count once). Built by pipeline/build_swap.py"}
    (HERE / "swap_export.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    from collections import Counter
    print(len(rows), "cases;", Counter((r[9], r[10]) for r in rows))
    print("investigation:", Counter(r[5] for r in rows), "return:", Counter(r[7] for r in rows))


if __name__ == "__main__":
    main()
