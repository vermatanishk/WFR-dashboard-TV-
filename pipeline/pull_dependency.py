"""
Pulls the Zoho Desk `Dependency` custom field (cf_dependency) per ticket into
zoho_raw90/ticket_dependency.json  ->  {ticket_id: "Warehouse" | "No Dependency" | ... | null}.

`Dependency` is set by the support agent at triage (values seen: Warehouse,
No Dependency, Logistics, Doc Pharma, Customer, CX Team, Finance, Management,
Category; null = never filled). It is the "warehouse dependency marked or not"
input for the RCA investigation funnel (build_rca.py). It is NOT an outcome
field - the sibling `Attribution` field sits at "Under Investigation" on ~all
tickets and is deliberately ignored.

Incremental: a ticket_id already present is never re-fetched EXCEPT null
values, which are retried until the ticket is 3+ days old (agents fill it in
after creation). Credentials: pipeline/.zoho.env (gitignored). No ticket body,
email or phone is read or stored - only the one field.

Run: python3 pipeline/pull_dependency.py
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoho_auth import desk_get, get_token

HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/ticket_dependency.json"


def fetch_one(ticket_id, tries=4):
    # searchTickets by ticketNumber - the short number in our data, NOT the
    # internal id (see CLAUDE.md). Pair by the returned ticketNumber, never position.
    for i in range(tries):
        try:
            rows = desk_get("/tickets/search", {"ticketNumber": ticket_id, "limit": 1}).get("data") or []
            for r in rows:
                if str(r.get("ticketNumber")) == str(ticket_id):
                    return ticket_id, ((r.get("cf") or {}).get("cf_dependency") or None), True
            return ticket_id, None, False
        except Exception:
            time.sleep(1.5 * (i + 1))
    return ticket_id, None, False


def main():
    get_token()
    tickets = json.loads((HERE / "data.json").read_text())["tickets"]
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    todo = []
    for t in tickets:
        tid = t["ticket_id"]
        created = datetime.fromisoformat(t["created_time"] + "+00:00")
        if tid not in cache or (cache[tid] is None and created > cutoff):
            todo.append(tid)
    print(f"{len(todo)} of {len(tickets)} tickets to fetch")
    done = failed = 0
    with ThreadPoolExecutor(6) as ex:
        for tid, dep, ok in ex.map(fetch_one, todo):
            if ok:
                cache[tid] = dep
                done += 1
            else:
                failed += 1
            if (done + failed) % 300 == 0:
                OUT.write_text(json.dumps(cache))
    OUT.write_text(json.dumps(cache))
    print(f"fetched {done}, failed {failed}, cache size {len(cache)}")
    if failed:
        print('Some fetches failed - fall back to the Zoho Desk MCP (searchTickets) for those ticket numbers.')


if __name__ == "__main__":
    main()
