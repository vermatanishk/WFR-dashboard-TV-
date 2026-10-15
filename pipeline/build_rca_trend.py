"""
Day-wise RCA view -> pipeline/rca_trend.json (website Tab 7) and pipeline/rca_view_spec.json (Google Sheet).

The view is a pure function of the order-level export: rca_export.json + the declarative layout in
rca_view_spec.py. Same pattern and T-2 cap as the Everything tab's macro table (frozen Metric | 3 month |
last month | last 2 weeks, then one column per day, most recent first). A global "Return request" selector
(All / Raised / Cancelled / Not raised) re-cuts every row. Cells are "count | % of parent row".
Run build_rca_export.py first.
"""
import json
from pathlib import Path

from rca_view_spec import RET_STATES, build_layout, evaluate, write_spec

HERE = Path(__file__).parent


def main():
    export = json.loads((HERE / "rca_export.json").read_text())
    layout = build_layout()
    trend = evaluate(export, layout)
    # Macro bucket 3 - return request - is a global cut: ship one full table per state so the website selector
    # (and the sheet's dropdown) re-cut EVERY row. "All" is the top level; the others live under by_return.
    trend["by_return"] = {s: evaluate(export, layout, s, days=trend["days"]) for s in RET_STATES}
    (HERE / "rca_trend.json").write_text(json.dumps(trend))
    write_spec(export=export)
    print(f"rca_trend.json: {len(trend['days'])} days, {len(trend['rows'])} rows, through {trend['t2_cutoff']}, held back {trend['excluded_tickets']}")
    for r in trend["rows"][:4]:
        print(" ", r["label"], r["3mo"]["text"])


if __name__ == "__main__":
    main()
