"""
Zoho Desk -> zoho_raw90/cmp_zoho_tickets.json: EVERY ticket created in the window (all dispositions), minimal fields only
(no names / phones / description text - the repo is public). One createdTimeRange search per UTC day, paged 100.
This is the Zoho half of the complaint baseline (build_complaints.py): the dashboard's data.json only holds the tickets whose
sub-disposition is in CATEGORY_MAP, which hid e.g. "Cold storage item delivered warm" / "Damaged packaging or container".

Per ticket: ticket_id, created_time (UTC), order_raw (cf_order_id text), disposition, sub_disposition, dependency, status, channel.
Order id is parsed later (build_full_dataset.parse_order_id). Idempotent: days already stored are skipped unless they are the
last 3 days (tickets still being edited) - delete the file to force a full pull.

Run: python3 pipeline/pull_complaint_tickets.py [start=2026-08-20]
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoho_auth import desk_get

HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/cmp_zoho_tickets.json"


def _clean_order(v):
    """Keep the order id only when it is a plain 6-9 digit number; free text may hold names / phones and the repo is public."""
    v = str(v or "").strip().rstrip(".")
    return v if re.fullmatch(r"\d{6,9}", v) else ("unparseable" if v else None)


def day_tickets(day):
    rows, frm = [], 1
    while True:
        for i in range(5):
            try:
                r = desk_get("/tickets/search", {"createdTimeRange": f"{day}T00:00:00.000Z,{day}T23:59:59.000Z", "limit": 100, "from": frm})
                break
            except Exception as ex:
                if "204" in str(ex) or "No Content" in str(ex):
                    return rows
                time.sleep(2 * (i + 1))
        else:
            raise RuntimeError(f"zoho search failed for {day} from {frm}")
        data = (r or {}).get("data") or []
        rows += data
        if len(data) < 100:
            return rows
        frm += 100
        if frm > 4800:
            raise RuntimeError(f"{day}: more than 4800 tickets in a day - split the range")


def main():
    start = datetime.strptime(sys.argv[1] if len(sys.argv) > 1 else "2026-08-20", "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    store = json.loads(OUT.read_text()) if OUT.exists() else {"days": {}}
    d = start
    while d <= today:
        k = d.isoformat()
        if k not in store["days"] or (today - d).days <= 3:
            rows = day_tickets(k)
            store["days"][k] = [{"ticket_id": t["ticketNumber"], "created_time": t["createdTime"], "order_raw": _clean_order((t.get("cf") or {}).get("cf_order_id")),
                                 "disposition": (t.get("cf") or {}).get("cf_dispositions"), "sub_disposition": (t.get("cf") or {}).get("cf_sub_disposition"),
                                 "dependency": (t.get("cf") or {}).get("cf_dependency"), "status": t.get("status"), "channel": t.get("channel")} for t in rows]
            print(k, len(rows), flush=True)
        d += timedelta(days=1)
    store["pulled_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps(store))
    print("done", sum(len(v) for v in store["days"].values()), "tickets")


if __name__ == "__main__":
    main()
