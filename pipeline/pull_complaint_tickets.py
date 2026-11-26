"""
Zoho Desk -> zoho_raw90/cmp_zoho_tickets.json: EVERY ticket created in the window (all dispositions), minimal fields only
(no names / phones / description text - the repo is public). One createdTimeRange search per UTC day, paged 100.
This is the Zoho half of the complaint baseline (build_complaints.py): the dashboard's data.json only holds the tickets whose
sub-disposition is in CATEGORY_MAP, which hid e.g. "Cold storage item delivered warm" / "Damaged packaging or container".

Per ticket: ticket_id, created_time (UTC), order_raw (cf_order_id text), disposition, sub_disposition, dependency, status, channel.
Order id is parsed later (build_full_dataset.parse_order_id). Idempotent: days already stored are skipped unless they are the
last 3 days (tickets still being edited) or were pulled less than 2 days after the day ended - delete the file to force a full pull.

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


def _window(t0, t1):
    """All tickets created in [t0, t1] (ISO, UTC). One page of 100 WITHOUT a `from` parameter: Zoho's `from` is a 0-based offset, so the old
    `from=1` silently skipped the first ticket of every query. A window that holds 100+ tickets is split in half, so no offset paging is needed."""
    for i in range(8):
        try:
            r = desk_get("/tickets/search", {"createdTimeRange": f"{t0},{t1}", "limit": 100})
            break
        except Exception as ex:
            if "204" in str(ex) or "No Content" in str(ex) or "JSONDecodeError" in repr(ex) or "Expecting value" in str(ex):
                return []
            time.sleep(3 * (i + 1))
    else:
        raise RuntimeError(f"zoho search failed for {t0} .. {t1}")
    data = (r or {}).get("data") or []
    if len(data) < 100:
        return data
    a = datetime.strptime(t0, "%Y-%m-%dT%H:%M:%S.000Z")
    b = datetime.strptime(t1, "%Y-%m-%dT%H:%M:%S.000Z")
    if (b - a).total_seconds() < 2:
        raise RuntimeError(f"{t0}: 100+ tickets in one second")
    mid = a + (b - a) / 2
    f = "%Y-%m-%dT%H:%M:%S.000Z"
    return _window(t0, mid.strftime(f)) + _window((mid + timedelta(seconds=1)).strftime(f), t1)


def day_tickets(day):
    """Every ticket of one UTC day. 2026-11-26: the old one-query-per-day offset paging (from=1,101,...) silently dropped ~1-2 tickets per day
    (and returned others twice) because Zoho's offset order is not stable; hourly windows with a recursive split are deterministic, then deduped by ticketNumber."""
    seen, out = set(), []
    for h in range(24):
        for t in _window(f"{day}T{h:02d}:00:00.000Z", f"{day}T{h:02d}:59:59.000Z"):
            if t["ticketNumber"] not in seen:
                seen.add(t["ticketNumber"])
                out.append(t)
    return out


def main():
    start = datetime.strptime(sys.argv[1] if len(sys.argv) > 1 else "2026-08-20", "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    store = json.loads(OUT.read_text()) if OUT.exists() else {"days": {}}
    d = start
    while d <= today:
        k = d.isoformat()
        # a day is final only if it was pulled at least 2 days AFTER it ended (fixes 2026-11-11: a day pulled mid-day and then
        # never revisited after a gap between sessions stayed partial, e.g. 2026-11-06 held 60 of ~170 tickets)
        pulled = (store.get("day_pulled") or {}).get(k)
        final = pulled is not None and (datetime.strptime(pulled, "%Y-%m-%d").date() - d).days >= 2
        if k not in store["days"] or (today - d).days <= 3 or not final:
            rows = day_tickets(k)
            fresh = [{"ticket_id": t["ticketNumber"], "created_time": t["createdTime"], "order_raw": _clean_order((t.get("cf") or {}).get("cf_order_id")),
                                 "disposition": (t.get("cf") or {}).get("cf_dispositions"), "sub_disposition": (t.get("cf") or {}).get("cf_sub_disposition"),
                                 "dependency": (t.get("cf") or {}).get("cf_dependency"), "status": t.get("status"), "channel": t.get("channel")} for t in rows]
            # UNION with what is already stored (never drop a ticket the earlier pulls / MCP fallback captured; fresh values win)
            prev = {t["ticket_id"]: t for t in store["days"].get(k, [])}
            prev.update({t["ticket_id"]: t for t in fresh})
            store["days"][k] = list(prev.values())
            store.setdefault("day_pulled", {})[k] = today.isoformat()
            print(k, len(rows), flush=True)
        d += timedelta(days=1)
    store["pulled_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps(store))
    print("done", sum(len(v) for v in store["days"].values()), "tickets")


if __name__ == "__main__":
    main()
