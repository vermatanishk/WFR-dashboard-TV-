"""
EOD tab, automated (2026-11-11). The hand-fed build_eod.py needed a session to paste every ticket + comment for each T-2 day; when nobody ran
it the tab froze on its last date (it sat on 2026-11-03 - with 0 accepted - for a week while real admissions kept happening).

This builds data_eod.json for for_date = (IST today - 2 days) from data we already refresh every day:
  tickets   data.json (5 mis-shipment categories, bucketed by the IST calendar day of created_time - same as the EOD convention)
  verdict   zoho_raw90/wh_text_check.json (Warehouse-role comment classifier: admitted / denied / no_wh_comment / unrecognized, re-read live by
            recheck_wh_comments.py) - the SAME classification rule as the hand-fed tab (first-person admission by the Warehouse role only)
  location / picker / qc   data.json
  packer / manifester      zoho_raw90/eod_chain.json (ClickHouse marketplace_order_status_log: ops_user_name at current_status_id 52 / 64, cached per
                           order). Only needed for admitted tickets; the script lists the orders missing from the cache.
Usage:  python3 pipeline/build_eod_auto.py [YYYY-MM-DD]     (default for_date = IST today - 2)
"""
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
data = json.loads((HERE / "data.json").read_text())
wh = json.loads((HERE / "zoho_raw90/wh_text_check.json").read_text())
chain_p = HERE / "zoho_raw90/eod_chain.json"
chain = json.loads(chain_p.read_text()) if chain_p.exists() else {}
for_date = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(IST).date() - timedelta(days=2)).isoformat()


def ist_day(created):
    return (datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=5, minutes=30)).date().isoformat()


out, need = [], []
for t in data["tickets"]:
    if ist_day(t["created_time"]) != for_date:
        continue
    v = wh.get(t["ticket_id"]) or {}
    verdict = v.get("verdict")
    acc = verdict == "admitted"
    texts = v.get("wh_texts") or ([v["evidence"]] if v.get("evidence") else [])
    comment = v.get("evidence") or (texts[-1] if texts else None)
    if acc:
        reason = f'Warehouse team comment is a genuine admission: "{comment}"'
    elif verdict == "denied":
        reason = f'Warehouse team comment: "{comment}" - this is a denial or non-admission (does not state WH sent the wrong/short item), not an admission. Not counted.'
    elif verdict == "unrecognized":
        reason = "Warehouse commented but it matches neither the admission nor the denial pattern - not counted."
    elif verdict == "no_wh_comment":
        reason = "No Warehouse-role comment on the ticket (only agent / L2 notes, if any) - not counted."
    else:
        reason = "Warehouse verdict not read yet - not counted."
    ch = chain.get(str(t["order_id"]), {}) if acc else {}
    if acc and str(t["order_id"]) not in chain:
        need.append(t["order_id"])
    out.append({"ticket_id": t["ticket_id"], "order_id": t["order_id"], "category": t["category"], "created_time": t["created_time"],
                "location": t.get("location") or "Unknown", "wh_comment": comment if verdict in ("admitted", "denied", "unrecognized") else None,
                "wh_accepted_text": acc, "reason": reason, "picker": t.get("picker") if acc else None, "packer": ch.get("packer"),
                "qc": t.get("qc") if acc else None, "manifester": ch.get("manifester")})
eod = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "for_date": for_date,
       "methodology": json.loads((HERE / "data_eod.json").read_text())["methodology"], "tickets": out}
(HERE / "data_eod.json").write_text(json.dumps(eod, indent=2))
acc = sum(1 for x in out if x["wh_accepted_text"])
print(f"for_date {for_date}: {len(out)} tickets, WH-Accepted (text) {acc}; verdicts", dict(Counter((wh.get(x['ticket_id']) or {}).get('verdict') for x in out)))
if need:
    print("packer/manifester missing for orders (pull status 52 / 64 from marketplace_order_status_log into zoho_raw90/eod_chain.json):", need)
