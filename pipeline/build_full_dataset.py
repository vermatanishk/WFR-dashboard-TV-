"""
Joins the exhaustive 90-day Zoho Desk ticket pull (zoho_raw90/consolidated.json)
with the chunked ClickHouse batch queries (zoho_raw90/ch_*.jsonl) to produce
pipeline/data.json, plus personnel leaderboard data (pipeline/personnel.json)
and a daily trend series (pipeline/trend.json).
"""
import json
from pathlib import Path
from collections import defaultdict
from category_mapping import WH_FAULT_CONFIRMED_REMARK_PATTERNS, NON_WH_FAULT_REMARK_PATTERNS

HERE = Path(__file__).parent


def load_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


tickets = json.loads((HERE / "zoho_raw90/consolidated.json").read_text())

returns = []
pickers_raw = []
qc_raw = []
for i in range(4):
    returns += load_jsonl(HERE / f"zoho_raw90/ch_returns_c{i}.jsonl")
    pickers_raw += load_jsonl(HERE / f"zoho_raw90/ch_pickers_c{i}.jsonl")
    qc_file_jsonl = HERE / f"zoho_raw90/ch_qc_c{i}.jsonl"
    qc_file_json = HERE / f"zoho_raw90/ch_qc_c{i}.json"
    if qc_file_json.exists():
        qc_raw += json.loads(qc_file_json.read_text())
    else:
        qc_raw += load_jsonl(qc_file_jsonl)

print(f"returns={len(returns)} pickers_raw={len(pickers_raw)} qc_raw={len(qc_raw)}")

returns_by_order = defaultdict(list)
for r in returns:
    returns_by_order[r["order_id"]].append(r)

pickers_by_order = defaultdict(dict)
for r in pickers_raw:
    if r["order_id"] is None:
        continue
    pickers_by_order[r["order_id"]][r["scanned_by_user_id"]] = r["picks"]

qc_by_order = defaultdict(list)
for r in qc_raw:
    if r.get("ops_user_name"):
        qc_by_order[r["order_id"]].append((r["ops_user_name"], r.get("user_id")))


def classify(order_id):
    rows = returns_by_order.get(order_id, [])
    if not rows:
        return "no_return_record", "Unknown", "No matching marketplace_return_request row found in ClickHouse for this order"

    locations = {(r["warehouse_name"], r["city"]) for r in rows if r["warehouse_name"]}
    location = ", ".join(n for n, c in locations) if locations else "Unknown"

    remarks = [r["remark"] for r in rows if r["remark"]]
    remark_l = " | ".join(remarks).lower()

    for pat in WH_FAULT_CONFIRMED_REMARK_PATTERNS:
        needle = pat.strip("%")
        if needle in remark_l:
            return "wh_accepted", location, f"remark matches WH-fault-confirmed pattern ('{needle}')"

    for pat in NON_WH_FAULT_REMARK_PATTERNS:
        needle = pat.strip("%")
        if needle in remark_l:
            return "bod", location, f"remark='{remarks[0]}' - explicit customer-favor/policy resolution, not a WH-fault admission"

    if remarks:
        return "considered_bod", location, f"remark='{remarks[0]}' is ambiguous/unrecognized - not confirmed WH-fault, treated as BOD by default"
    return "considered_bod", location, "return exists but remark is empty - treated as BOD by default (unconfirmed resolution)"


def picker_str(order_id):
    picks = pickers_by_order.get(order_id)
    if not picks:
        return None
    mx = max(picks.values())
    top = [uid for uid, n in picks.items() if n == mx]
    return top


def qc_info(order_id):
    entries = qc_by_order.get(order_id)
    if not entries:
        return None
    return entries[0]


user_wh = {}
for r in load_jsonl(HERE / "zoho_raw90/user_warehouse_map.jsonl"):
    user_wh[r["internal_user_id"]] = r["warehouse_name"]

out_tickets = []
for t in tickets:
    order_id = int(t["order_id"])
    resolution, location, reason_note = classify(order_id)
    accepted = resolution == "wh_accepted"
    pick_uids = picker_str(order_id) if accepted else None
    qc = qc_info(order_id) if accepted else None
    picker_display = " / ".join(f"user_{u}" for u in pick_uids) if pick_uids else None
    out_tickets.append({
        "ticket_id": t["ticket_id"],
        "order_id": order_id,
        "category": t["category"],
        "location": location,
        "created_time": t["created_time"].replace("Z", ""),
        "resolution": resolution,
        "accepted": accepted,
        "accept_reason": reason_note,
        "picker": picker_display,
        "picker_ids": pick_uids or [],
        "qc": qc[0] if qc else None,
        "qc_id": qc[1] if qc else None,
    })

data = {
    "generated_at": "2026-07-27T12:00:00Z",
    "sheet_source": "Zoho Desk API (live) via connected MCP - org 60026539570, department Support",
    "clickhouse_service": "PRx Nucleus",
    "pull_window": "Last 90 days (2026-04-28 to 2026-07-27), exhaustive within that window",
    "sample_note": f"Exhaustive pull of all mis-shipment tickets from the live Zoho Desk API for the trailing 90 days (2026-04-28 to 2026-07-27) - {len(out_tickets)} tickets across 5 categories, not a sample. Location and resolution (WH-Accepted / BOD / Considered BOD) are computed live against ClickHouse for every order. 'Considered BOD' = a return exists but the remark was ambiguous or blank, so it defaults to BOD rather than a confirmed WH-fault admission. Switch Orders found 0 tickets in this window.",
    "tickets": out_tickets,
}
(HERE / "data.json").write_text(json.dumps(data))
print(f"Wrote {len(out_tickets)} tickets to data.json")

from collections import Counter
print("By resolution:", Counter(t["resolution"] for t in out_tickets))

# ---- Personnel leaderboard (accepted orders only, grouped by warehouse) ----
picker_totals = {}
for line in open(HERE / "zoho_raw90/picker_totals.csv"):
    line = line.strip()
    if not line or line.startswith("user_id"): continue
    uid, total = line.split(",")
    picker_totals[int(uid)] = int(total)

qc_totals = {}
for line in open(HERE / "zoho_raw90/qc_totals.csv"):
    line = line.strip()
    if not line or line.startswith("user_id"): continue
    parts = line.split(",")
    uid, total = parts[0], parts[-1]
    qc_totals[int(uid)] = int(total)

picker_errors = defaultdict(int)
qc_errors = defaultdict(int)
for t in out_tickets:
    if not t["accepted"]:
        continue
    for uid in t["picker_ids"]:
        picker_errors[uid] += 1
    if t["qc_id"]:
        qc_errors[t["qc_id"]] += 1

by_wh_pickers = defaultdict(list)
for uid, errors in picker_errors.items():
    wh = user_wh.get(uid, "Unknown")
    total = picker_totals.get(uid, 0)
    by_wh_pickers[wh].append({
        "user_id": uid, "total_orders": total, "error_orders": errors,
        "error_free_orders": max(total - errors, 0),
        "error_rate_pct": round(100 * errors / total, 2) if total else None,
    })

by_wh_qc = defaultdict(list)
for uid, errors in qc_errors.items():
    wh = user_wh.get(uid, "Unknown")
    total = qc_totals.get(uid, 0)
    name = next((r.get("name") for r in [{}] ), None)
    by_wh_qc[wh].append({
        "user_id": uid, "total_orders": total, "error_orders": errors,
        "error_free_orders": max(total - errors, 0),
        "error_rate_pct": round(100 * errors / total, 2) if total else None,
    })

# attach names for qc
qc_names = {}
for line in open(HERE / "zoho_raw90/qc_totals.csv"):
    line = line.strip()
    if not line or line.startswith("user_id"): continue
    parts = line.split(",")
    qc_names[int(parts[0])] = parts[1]
for wh, rows_ in by_wh_qc.items():
    for r in rows_:
        r["name"] = qc_names.get(r["user_id"], f"user_{r['user_id']}")

for wh, rows_ in by_wh_pickers.items():
    rows_.sort(key=lambda r: -r["error_orders"])
for wh, rows_ in by_wh_qc.items():
    rows_.sort(key=lambda r: -r["error_orders"])

personnel = {"pickers_by_warehouse": by_wh_pickers, "qc_by_warehouse": by_wh_qc}
(HERE / "personnel.json").write_text(json.dumps(personnel))
print("Wrote personnel.json:", {k: len(v) for k, v in by_wh_pickers.items()})

# ---- Daily trend (raised vs accepted, by category) ----
trend = defaultdict(lambda: defaultdict(lambda: {"raised": 0, "accepted": 0}))
for t in out_tickets:
    day = t["created_time"][:10]
    trend[day]["All"]["raised"] += 1
    trend[day][t["category"]]["raised"] += 1
    if t["accepted"]:
        trend[day]["All"]["accepted"] += 1
        trend[day][t["category"]]["accepted"] += 1

trend_out = []
for day in sorted(trend.keys()):
    row = {"date": day}
    row["series"] = trend[day]
    trend_out.append(row)
(HERE / "trend.json").write_text(json.dumps(trend_out))
print("Wrote trend.json:", len(trend_out), "days")
