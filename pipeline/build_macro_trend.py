"""
Builds pipeline/macro_trend.json for Tab 1's "Everything" macro trend table -
a filter-free, whole-network view: Delivered Orders, Return Requested (%% of
delivered), WH Accepted, Total WFR (WH-accepted errors per 1,000 delivered
orders - highlighted yellow on the dashboard), and WH Accepted broken down
into the 5 categories that sum to it. No date range / category / location
filters apply to this table on purpose - it's the one place on the
dashboard meant to show the unfiltered whole picture.

Columns: 3-month total | last-month total | last-2-weeks total | then one
column per day, most recent complete day first, going backwards. The current
(partial) day is excluded from every column so a half-finished day never
drags a rate down - see DELIVERED_PATH note below.

Delivered-orders counts come from ClickHouse `marketplace_order_status_log`
(current_status_id = 70, i.e. the order actually reached "delivered" - NOT
`created_at` on marketplace_orders, which is order *creation*, not delivery -
saved to zoho_raw90/ch_delivered_daily.json:
    SELECT toDate(created_at) AS day, count(DISTINCT order_id) AS delivered_orders
    FROM prx_prod_db.marketplace_order_status_log
    WHERE current_status_id = 70 AND created_at >= toDateTime('<start>')
      AND created_at < toDateTime('<end, exclusive>')
    GROUP BY day ORDER BY day
Re-run this query and overwrite the file when refreshing past its date range.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

CATEGORY_ORDER = [
    ("Missing/Wrong Qty", "Missing or Short Qty"),
    ("Wrong Medicines", "Wrong Item Received"),
    ("Expiry Issue", "Expired or near Expiry"),
    ("Damaged/Defective", "Damaged"),
    ("Switch Orders", "Order Swap"),
]

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def day_label(d):
    y, m, day = d.split("-")
    return f"{int(day)} {MONTHS[int(m) - 1]}"


def accepted_cell(raised, accepted):
    pct = f"{round(100 * accepted / raised)}%" if raised else "–"
    return {"raised": raised, "accepted": accepted, "pct": pct, "text": f"{raised} | {accepted} ({pct})" if raised else "0 | 0 (–)"}


def rate_cell(raised, denom):
    pct = f"{round(100 * raised / denom, 1)}%" if denom else "–"
    return {"raised": raised, "denom": denom, "pct": pct, "text": f"{raised} | {pct}" if denom else f"{raised} | –"}


def wfr_pto_cell(accepted, delivered):
    # WFR PTO = WH-accepted errors per thousand delivered orders.
    value = round(1000 * accepted / delivered, 2) if delivered else None
    return {"accepted": accepted, "delivered": delivered, "value": value, "text": f"{value:.2f}" if value is not None else "–"}


def sum_cells(cells):
    raised = sum(c["raised"] for c in cells)
    return raised


def main():
    data = json.loads((HERE / "data.json").read_text())
    tickets = data["tickets"]

    delivered_path = HERE / "zoho_raw90/ch_delivered_daily.json"
    delivered_daily = json.loads(delivered_path.read_text()) if delivered_path.exists() else {}

    # Delivered-daily's own date range is the source of truth for which days
    # this table covers (tickets are pulled for the same/a subset window).
    # Drop the most recent day - it's always partial (today, mid-refresh) -
    # so a half-finished day never shows up as a cliff/spike that isn't real.
    days = sorted(delivered_daily.keys())[:-1]
    days_set = set(days)

    raised_by_day = defaultdict(int)
    accepted_by_day = defaultdict(int)
    raised_cat_by_day = defaultdict(lambda: defaultdict(int))
    accepted_cat_by_day = defaultdict(lambda: defaultdict(int))

    for t in tickets:
        day = t["created_time"][:10]
        if day not in days_set:
            continue
        cat = t["category"]
        raised_by_day[day] += 1
        raised_cat_by_day[day][cat] += 1
        if t["accepted"]:
            accepted_by_day[day] += 1
            accepted_cat_by_day[day][cat] += 1

    def window(n):
        return days[-n:] if n else days

    def delivered_sum(day_list):
        return sum(delivered_daily.get(d, 0) for d in day_list)

    def build_row(label, sub, is_rate_row, cat_key=None):
        def cell_for(day_list):
            raised = sum(raised_cat_by_day[d].get(cat_key, 0) if cat_key else raised_by_day[d] for d in day_list)
            if is_rate_row:
                return rate_cell(raised, delivered_sum(day_list))
            accepted = sum(accepted_cat_by_day[d].get(cat_key, 0) if cat_key else accepted_by_day[d] for d in day_list)
            return accepted_cell(raised, accepted)

        row = {
            "label": label, "sub": sub,
            "3mo": cell_for(days),
            "1mo": cell_for(window(30)),
            "2wk": cell_for(window(14)),
            "daily": {d: cell_for([d]) for d in days},
        }
        return row

    rows = []
    rows.append({
        "label": "Delivered Orders", "sub": None, "kind": "plain",
        "3mo": delivered_sum(days), "1mo": delivered_sum(window(30)), "2wk": delivered_sum(window(14)),
        "daily": {d: delivered_daily.get(d, 0) for d in days},
    })
    rows.append({**build_row("Return Requested", "(Total Raised | % of delivered orders)", is_rate_row=True), "kind": "rate"})
    rows.append({**build_row("WH Accepted", "(Total raised | WH accepted (% of raised))", is_rate_row=False), "kind": "accept"})

    def wfr_pto_for(day_list):
        accepted = sum(accepted_by_day[d] for d in day_list)
        return wfr_pto_cell(accepted, delivered_sum(day_list))

    rows.append({
        "label": "Total WFR", "sub": "(WH-accepted errors per 1,000 delivered orders)", "kind": "wfr_pto",
        "3mo": wfr_pto_for(days), "1mo": wfr_pto_for(window(30)), "2wk": wfr_pto_for(window(14)),
        "daily": {d: wfr_pto_for([d]) for d in days},
    })

    for cat_key, cat_label in CATEGORY_ORDER:
        rows.append({**build_row(cat_label, "(Raised | Accepted count (Accept %))", is_rate_row=False, cat_key=cat_key), "kind": "accept"})

    out = {
        "days": days,  # ascending; oldest first
        "day_labels": {d: day_label(d) for d in days},
        "rows": rows,
    }
    (HERE / "macro_trend.json").write_text(json.dumps(out))
    print(f"Wrote macro_trend.json: {len(days)} days, {len(rows)} rows")


if __name__ == "__main__":
    main()
