"""
Substitutes the fresh JSON datasets into pipeline/dashboard.html's placeholders
to produce pipeline/dashboard_built.html, then copies it to the repo-root
index.html (which Vercel serves at /).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent

template = (HERE / "dashboard.html").read_text()

files = {
    "__AGGREGATES_JSON__": "aggregates.json",
    "__TICKETS_JSON__": "data.json",
    "__PERSONNEL_JSON__": "personnel.json",
    "__TREND_JSON__": "trend.json",
    "__ORDERS_BY_DAY_JSON__": "orders_by_day.json",
    "__ORDERS_BY_DAY_LOCATION_JSON__": "orders_by_day_location.json",
    "__EOD_JSON__": "data_eod.json",
}

out = template
for placeholder, fname in files.items():
    payload = json.loads((HERE / fname).read_text())
    if placeholder == "__TICKETS_JSON__":
        payload = payload["tickets"]
    marker_count = out.count(placeholder)
    if marker_count != 1:
        raise SystemExit(f"Expected exactly 1 occurrence of {placeholder}, found {marker_count}")
    out = out.replace(placeholder, json.dumps(payload))

(HERE / "dashboard_built.html").write_text(out)
(ROOT / "index.html").write_text(out)
print(f"Wrote pipeline/dashboard_built.html and index.html ({len(out)} bytes)")
