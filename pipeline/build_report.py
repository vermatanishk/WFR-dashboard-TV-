"""
Computes Tab1/Tab2 aggregates from pipeline/data.json and writes:
  - pipeline/aggregates.json  (feeds the dashboard - all-time; the dashboard itself
    re-filters client-side for the date-range buttons)
  - pipeline/wfr_daily_report.csv  (the downloadable ops report)

Personnel leaderboards (Tab 3) and the trend series (Tab 1 chart) are computed
separately by build_full_dataset.py into personnel.json / trend.json, since
they depend on ClickHouse-wide picker/QC totals, not just the ticket set.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
data = json.loads((HERE / "data.json").read_text())
tickets = data["tickets"]

CATEGORIES = ["Missing/Wrong Qty", "Wrong Medicines", "Expiry Issue", "Damaged/Defective", "Switch Orders"]


def compute(tickets):
    total_tickets = len(tickets)
    total_orders = len({t["order_id"] for t in tickets})

    with_return = [t for t in tickets if t["resolution"] != "no_return_record"]
    wh_accepted = [t for t in tickets if t["resolution"] == "wh_accepted"]
    bod = [t for t in tickets if t["resolution"] == "bod"]
    considered_bod = [t for t in tickets if t["resolution"] == "considered_bod"]
    no_return = [t for t in tickets if t["resolution"] == "no_return_record"]

    total_returns = len(with_return)
    reconciles = (len(wh_accepted) + len(bod) + len(considered_bod)) == total_returns

    by_category = defaultdict(lambda: {"total": 0, "accepted": 0})
    for t in tickets:
        by_category[t["category"]]["total"] += 1
        if t["resolution"] == "wh_accepted":
            by_category[t["category"]]["accepted"] += 1

    tab1_by_category = []
    for cat in CATEGORIES:
        row = by_category.get(cat, {"total": 0, "accepted": 0})
        pct_of_total = round(100 * row["total"] / total_tickets, 1) if total_tickets else 0
        accept_pct = round(100 * row["accepted"] / row["total"], 1) if row["total"] else 0
        tab1_by_category.append({
            "category": cat, "total": row["total"], "pct_of_total": pct_of_total,
            "accepted": row["accepted"], "accept_pct": accept_pct,
        })

    by_location = defaultdict(lambda: {"total": 0, "accepted": 0})
    for t in tickets:
        by_location[t["location"]]["total"] += 1
        if t["resolution"] == "wh_accepted":
            by_location[t["location"]]["accepted"] += 1
    tab2 = []
    for loc, row in sorted(by_location.items(), key=lambda kv: -kv[1]["total"]):
        pct = round(100 * row["accepted"] / row["total"], 1) if row["total"] else 0
        tab2.append({"location": loc, "total": row["total"], "accepted": row["accepted"], "accept_pct": pct})

    return {
        "tab1": {
            "total_tickets": total_tickets,
            "total_orders": total_orders,
            "total_returns": total_returns,
            "wh_accepted": len(wh_accepted),
            "bod": len(bod),
            "considered_bod": len(considered_bod),
            "no_return_record": len(no_return),
            "accept_pct": round(100 * len(wh_accepted) / total_orders, 1) if total_orders else 0,
            "reconciles": reconciles,
            "by_category": tab1_by_category,
        },
        "tab2": tab2,
    }


aggregates = {
    "generated_at": data["generated_at"],
    "sample_note": data["sample_note"],
    "pull_window": data.get("pull_window", ""),
    **compute(tickets),
}
(HERE / "aggregates.json").write_text(json.dumps(aggregates, indent=2))

RESOLUTION_LABEL = {"wh_accepted": "WH Accepted", "bod": "BOD", "considered_bod": "Considered BOD", "no_return_record": "No return record"}

with open(HERE / "wfr_daily_report.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["WFR Daily Report", data["generated_at"]])
    w.writerow([])
    w.writerow(["Ticket ID", "Order ID", "Category", "Location", "Created Time", "Resolution", "Reason", "Picker", "QC Checker"])
    for t in tickets:
        w.writerow([t["ticket_id"], t["order_id"], t["category"], t["location"], t["created_time"], RESOLUTION_LABEL[t["resolution"]], t["accept_reason"], t["picker"] or "-", t["qc"] or "-"])
    w.writerow([])
    w.writerow(["Summary"])
    w.writerow(["Total tickets raised", aggregates["tab1"]["total_tickets"]])
    w.writerow(["Total refunds/returns issued", aggregates["tab1"]["total_returns"]])
    w.writerow(["WH Accepted", aggregates["tab1"]["wh_accepted"]])
    w.writerow(["BOD", aggregates["tab1"]["bod"]])
    w.writerow(["Considered BOD", aggregates["tab1"]["considered_bod"]])
    w.writerow(["No return record (excluded from refund total)", aggregates["tab1"]["no_return_record"]])
    w.writerow(["Reconciles (WH Accepted + BOD + Considered BOD == Total refunds/returns)", "Yes" if aggregates["tab1"]["reconciles"] else "NO - CHECK DATA"])

print("Wrote aggregates.json and wfr_daily_report.csv")
print(json.dumps(aggregates["tab1"], indent=2))
