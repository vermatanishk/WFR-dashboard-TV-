"""
Order-swap ticket scan (Zoho Desk REST) -> zoho_raw90/swap_tickets.json.

Agents historically filed swaps as Wrong Medicine / Wrong item Delivered, so the scan is TEXT based (subject +
description wildcards) plus the new "Order Swap" sub-disposition. Stores only IDs, dates, disposition fields and
the matched keyword kind - never the description text, names or phones (the repo is public).

Per ticket: ticket_id, created (UTC date), own order (cf_order_id), other_orders (7-digit ids found in the text),
sub_disposition, disposition, dependency, signals (list of matched patterns), noise flag.
Playbook: order-swap playbook (section 3). "wrong cx received wrong medicine instead of X" = single-item mix-up = noise.

Run: python3 pipeline/pull_swap_tickets.py [days=60]
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoho_auth import desk_get

HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/swap_tickets.json"
QUERIES = [("subject", "*swap*"), ("subject", "*swipe*"), ("description", "*swap*"), ("description", "*swipe*"),
           ("description", "*another cx*"), ("description", "*other cx*"), ("description", "*someone else*"),
           ("description", "*another customer*"), ("description", "*other customer*"), ("description", "*different order*"),
           ("description", "*mixed up*"), ("description", "*other person*")]
STRONG = re.compile(r"swap|swipe|another cx|other cx|someone else|any one else|different order|another customer|other customer|other person|mixed up|instead of \d{7}|label (?:is|of)", re.I)
OID = re.compile(r"(?<!\d)([34]\d{6})(?!\d)")
NOISE_WRONGMED = re.compile(r"wrong (?:cx|medicine).{0,40}instead of", re.I)


def search(field, pat, a, b):
    rows, frm = [], 1
    while True:
        for i in range(4):
            try:
                r = desk_get("/tickets/search", {field: pat, "createdTimeRange": f"{a}T00:00:00.000Z,{b}T23:59:00.000Z", "limit": 100, "from": frm})
                break
            except Exception as ex:
                if "204" in str(ex) or "No Content" in str(ex):
                    return rows
                time.sleep(2 * (i + 1))
        else:
            return rows
        data = (r or {}).get("data") or []
        rows += data
        if len(data) < 100:
            return rows
        frm += 100


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    found = {}
    d = start
    while d <= end:
        e = min(d + timedelta(days=2), end)
        for field, pat in QUERIES:
            for t in search(field, pat, d.isoformat(), e.isoformat()):
                found.setdefault(t["ticketNumber"], t)
        print(d, e, len(found), flush=True)
        d = e + timedelta(days=1)
    out = []
    for tn, t in found.items():
        cf = t.get("cf") or {}
        text = re.sub(r"<[^>]+>", " ", (t.get("subject") or "") + " " + (t.get("description") or ""))
        text = re.sub(r"Contact No:\s*\d+", " ", text)
        own = str(cf.get("cf_order_id") or "").strip()
        ids = [x for x in dict.fromkeys(OID.findall(text))]
        sig = sorted({m.group(0).lower() for m in STRONG.finditer(text)})
        sub = cf.get("cf_sub_disposition")
        is_swap_disp = (sub or "").lower() in ("order swap", "order swapped")
        noise = bool(NOISE_WRONGMED.search(text)) and not is_swap_disp and not any(x != own for x in ids) and not re.search(r"swap|swipe|another|someone", text, re.I)
        out.append({"ticket_id": tn, "created": t["createdTime"][:10], "created_time": t["createdTime"], "order_id": own,
                    "other_orders": [x for x in ids if x != own], "sub_disposition": sub, "disposition": cf.get("cf_dispositions"),
                    "dependency": cf.get("cf_dependency"), "signals": sig, "order_swap_disposition": is_swap_disp, "noise": noise})
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "start": start.isoformat(),
                               "end": end.isoformat(), "tickets": sorted(out, key=lambda x: x["ticket_id"])}, separators=(",", ":")))
    print("tickets", len(out), "with other order", sum(1 for x in out if x["other_orders"]), "swap disp", sum(x["order_swap_disposition"] for x in out))


if __name__ == "__main__":
    main()
