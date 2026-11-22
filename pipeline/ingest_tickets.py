"""
Merge tickets read through the Zoho Desk MCP (REST unavailable) into zoho_raw90/cmp_zoho_tickets.json - same record shape as
pull_complaint_tickets.py. Input text lines:  <ticketNumber>|<HH:MM:SS UTC>|<order id or empty>|<sub-disposition>[|<dependency>]
  python3 pipeline/ingest_tickets.py <YYYY-MM-DD> <file>   replaces that day's list with the file (day marked pulled today)
Only the Return and Pickup disposition is fetched this way (99% of complaint-type tickets); other dispositions of that day are kept
from any earlier REST pull of the same day.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
P = HERE / "zoho_raw90/cmp_zoho_tickets.json"


def main(day, path):
    store = json.loads(P.read_text())
    new = []
    for ln in Path(path).read_text().splitlines():
        if not ln.strip():
            continue
        f = ln.split("|")
        num, hms, oid, sub = f[0], f[1], f[2], f[3]
        dep = f[4] if len(f) > 4 else None
        new.append({"ticket_id": num, "created_time": f"{day}T{hms}.000Z", "order_raw": (oid or None), "disposition": "Return and Pickup",
                    "sub_disposition": sub, "dependency": dep, "status": None, "channel": None, "source": "zoho-mcp"})
    ids = {t["ticket_id"] for t in new}
    keep = [t for t in store["days"].get(day, []) if t["ticket_id"] not in ids and t.get("disposition") != "Return and Pickup"]
    store["days"][day] = keep + new
    store["day_pulled"][day] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    store["pulled_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    P.write_text(json.dumps(store))
    print(day, len(new), "Return-and-Pickup tickets merged;", len(keep), "other-disposition tickets kept")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
