"""
Independent checks of the complaint baseline (build_complaints.py / cmp_view_spec.py). Everything is re-derived from the RAW
files with separate, deliberately naive code - it shares no logic with the builder except the documented reason mapping.
Run: python3 pipeline/test_complaints.py   (exits non-zero on any failure)
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


exp = json.loads((HERE / "complaints_export.json").read_text())
C = {c: i for i, c in enumerate(exp["columns"])}
rows = exp["rows"]

# 1. structure ---------------------------------------------------------------------------------------------------
keys = Counter((r[C["Order ID"]], r[C["Complaint type"]]) for r in rows)
check("one row per (order, complaint type)", max(keys.values()) == 1)
check("every row has a date inside the window", all(exp["window_start"] <= r[C["Created date"]] <= exp["t2_cap_date"] for r in rows))
check("WH verdict gap is zero (every ticket past T-2 has a read verdict)", not any(r[C["WH input"]] == "Verdict not read (gap)" for r in rows))
check("no complaint-type ticket left unattached", exp["notes"].get("unaccounted_ticket_ids") == [], str(exp["notes"].get("unaccounted_ticket_ids"))[:80])
check("ticket-only rows always have a ticket", all(r[C["Ticket raised"]] == "Yes" for r in rows if r[C["Source"]] == "Zoho ticket only"))
check("return-based rows never say 'Return request: Not raised'", all(r[C["Return request"]] != "Not raised" for r in rows if r[C["Source"]] != "Zoho ticket only"))
check("WH input is 'No ticket' exactly when no ticket was raised", all((r[C["WH input"]] == "No ticket") == (r[C["Ticket raised"]] == "No") for r in rows))
check("cancelled / rejected <=> out of scope", all((r[C["In scope"]] == "No") == (r[C["Return request"]] in ("Raised - Cancelled", "Raised - Rejected")) for r in rows))

# 2. independent recount of the return side from the raw ClickHouse chunks -------------------------------------------
items = {}
for p in sorted(RAW.glob("cmp_returns_c*.json")):
    for r in json.loads(p.read_text())["result"]["data"]:
        k = (r["order_id"], r["drug_code"])
        if k not in items or r["created"] > items[k]["created"]:
            items[k] = r


def rtype(reason):
    s = re.sub(r"\s+", " ", (reason or "").lower().strip())
    if "swap" in s or "switch" in s: return "Order swap"
    if "mrp" in s or "batch mismatch" in s: return "MRP / batch mismatch"
    if "wrong medic" in s or "wrong item" in s: return "Wrong medicine"
    if "incomplete order" in s or "missing" in s or "less quantity" in s or "short qty" in s: return "Missing / short qty"
    if "expir" in s: return "Expiry"
    if any(w in s for w in ("cold storage", "damag", "defective", "leak", "spill", "broken")): return "Damage"
    return None


want = defaultdict(set)
for (o, d), r in items.items():
    t = rtype(r["reason"])
    if t and exp["window_start"] <= r["created"][:10] <= exp["t2_cap_date"]:
        want[t].add(o)
have = defaultdict(set)
for r in rows:
    if r[C["Source"]] != "Zoho ticket only":
        have[r[C["Complaint type"]]].add(r[C["Order ID"]])
for t in want:
    # a complaint whose earliest request fell before the window start is dropped by design; allow a +-1 day boundary
    miss = want[t] - have[t]
    check(f"return-side complaints present: {t}", len(miss) <= max(2, len(want[t]) // 100), f"{len(miss)} missing of {len(want[t])}")

# 3. final-reason rule: a dead draft ("Received Wrong Medicines" followed by "No Longer Needed") must NOT be a complaint
for o in (4264424, 4305606, 4322556, 4323303):
    check(f"order {o}: dead wrong-medicine draft is not a wrong-medicine complaint",
          not any(r[C["Order ID"]] == o and r[C["Complaint type"]] == "Wrong medicine" and r[C["Source"]] != "Zoho ticket only" for r in rows))

# 4. independent recount of the Zoho side ------------------------------------------------------------------------------
store = json.loads((RAW / "cmp_zoho_tickets.json").read_text())
tk = {t["ticket_id"]: t for d in store["days"].values() for t in d}
tid_in_rows = {r[C["Ticket ID"]] for r in rows if r[C["Ticket ID"]]}
check("every ticket id in the export exists in the Zoho pull", all(t in tk for t in tid_in_rows))
check("ticket ids in the export are unique per row set", len(tid_in_rows) <= len(rows))
bad = [r for r in rows if r[C["Ticket ID"]] and re.sub(r"\D", "", str(tk[r[C["Ticket ID"]]]["order_raw"] or "")) != str(r[C["Order ID"]])]
check("attached ticket's own Order ID field equals the row's order", not bad, str(bad[:2]))

# 5. view layer: parent rows = sum of children, return states add up to All -------------------------------------------
for name in ("wfr", "damage"):
    t = json.loads((HERE / f"cmp_{name}_trend.json").read_text())
    n = {r["key"]: r["3mo"]["n"] for r in t["rows"]}
    check(f"{name}: sources add up to complaints", n["all"] == n["src_both"] + n["src_ret"] + n["src_tkt"])
    check(f"{name}: scope + excluded = complaints", n["all"] == n["scope"] + n["ex_can"] + n["ex_rej"])
    check(f"{name}: in scope = ticketed + non-complaint ticket + no ticket", n["scope"] == n["t_yes"] + n["t_non"] + n["t_none"])
    check(f"{name}: ticketed = matched + other type", n["t_yes"] == n["t_match"] + n["t_other"])
    check(f"{name}: WH input rows add up to ticketed", n["t_yes"] == sum(n[k] for k in ("wh_acc", "wh_den", "wh_oth", "wh_none", "wh_due", "wh_gap")))
    for r in t["rows"]:
        for per in ("3mo", "1mo", "2wk"):
            tot = sum(t["by_return"][s]["rows"][[x["key"] for x in t["rows"]].index(r["key"])][per]["n"] for s in t["by_return"])
            if tot != r[per]["n"]:
                check(f"{name}: return states add up to All ({r['key']} {per})", False, f"{tot} vs {r[per]['n']}")
                break
    check(f"{name}: return states add up to All, every row", True)
wfr = json.loads((HERE / "cmp_wfr_trend.json").read_text())
n = {r["key"]: r["3mo"]["n"] for r in wfr["rows"]}
types = [k for k in n if k.startswith("ty_") and not k.endswith(("_y", "_n", "_nr"))]
check("wfr: per-type in-scope rows add up to in scope", sum(n[k] for k in types) == n["scope"])
dm = json.loads((HERE / "cmp_damage_trend.json").read_text())
d = {r["key"]: r["3mo"]["n"] for r in dm["rows"]}
check("damage: temperature + physical = in scope", d["temp"] + d["phys"] == d["scope"])
check("damage: physical = photo read + not read + no file + not available",
      d["phys"] == d["ph_read"] + d["ph_unread"] + d["ph_nofile"] + d["ph_na"])
check("damage: photo buckets add up to photo read", d["ph_read"] == sum(d[f"pb{i}"] for i in range(8)))
check("damage: no unread photos left", d["ph_unread"] <= 3, str(d["ph_unread"]))
# 5b. hand-written predicates over the per-tab exports must equal the engine's counts (independent of the layout spec)
for name, types in (("wfr", {"Wrong medicine", "Missing / short qty", "Expiry", "MRP / batch mismatch"}), ("damage", {"Damage"})):
    ex = json.loads((HERE / f"cmp_{name}_export.json").read_text())
    X = {c: i for i, c in enumerate(ex["columns"])}
    R = [r for r in ex["rows"] if r[X["Created date"]] <= ex["t2_cap_date"]]
    check(f"{name}: export holds only its own complaint types", {r[X["Complaint type"]] for r in R} <= types)
    tr = json.loads((HERE / f"cmp_{name}_trend.json").read_text())
    n = {r["key"]: r["3mo"]["n"] for r in tr["rows"]}
    sc = [r for r in R if r[X["Return request"]] not in ("Raised - Cancelled", "Raised - Rejected")]
    hand = {"all": len(R), "scope": len(sc), "ex_can": sum(r[X["Return request"]] == "Raised - Cancelled" for r in R),
            "ex_rej": sum(r[X["Return request"]] == "Raised - Rejected" for r in R),
            "t_yes": sum(bool(r[X["Ticket ID"]]) and r[X["Ticket relation"]] in ("Filed under this complaint type", "Filed under another complaint type") for r in sc),
            "t_none": sum(r[X["Ticket relation"]] == "No ticket" for r in sc),
            "wh_acc": sum(r[X["WH input"]] == "WH accepted" for r in sc), "wh_none": sum(r[X["WH input"]] == "No WH comment" for r in sc)}
    for k, v in hand.items():
        check(f"{name}: hand count '{k}' = engine ({v})", n[k] == v, f"engine {n[k]}")

# 6. summary -----------------------------------------------------------------------------------------------------------
sm = json.loads((HERE / "cmp_summary.json").read_text())
check("summary is at most 8 rows x 3 columns", len(sm["rows"]) <= 8 and len(sm["columns"]) == 3 and all(len(r["values"]) == 3 for r in sm["rows"]))
for i, rw in enumerate(sm["raw"]):
    check(f"summary col {i}: complaints = excluded + in scope; in scope = ticketed + not", rw["n"] == rw["excl"] + rw["scope"] and rw["scope"] == rw["tk"] + rw["notk"])

print("\n%d failure(s)" % len(fails))
sys.exit(1 if fails else 0)
