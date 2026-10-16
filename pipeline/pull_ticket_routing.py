"""
Routing signals per ticket -> zoho_raw90/ticket_routing.json
  {ticket_id: {"dependency", "dependency_ever": [...], "tags_now": [...], "tags_ever": [...], "fetched_on"}}
Used by build_rca.py: a ticket counts as "routed to the Warehouse" when its Dependency is Warehouse NOW, was ever
Warehouse in the ticket History (agents change it later), or ever carried a warehouse tag (`blr wh`, `kt wh`, ...).
Candidates = RCA rows with no WH verdict yet (not_investigated) whose current Dependency is not Warehouse.
Incremental; tickets younger than 5 days are re-fetched (dependency / tags are set after creation).
Only labels are stored - no comment text.   Run: python3 pipeline/pull_ticket_routing.py
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zoho_auth import desk_get

HERE = Path(__file__).parent
OUT = HERE / "zoho_raw90/ticket_routing.json"


def fetch_routing(tn, tries=3):
    for i in range(tries):
        try:
            hit = next((h for h in desk_get("/tickets/search", {"ticketNumber": tn, "limit": 1}).get("data", [])
                        if str(h["ticketNumber"]) == str(tn)), None)
            if not hit:
                return None
            tid = hit["id"]
            tags_now = [t["name"] for t in desk_get(f"/tickets/{tid}/tags").get("tags", [])]
            deps, tags, frm = [], set(tags_now), 1
            cur = (hit.get("cf") or {}).get("cf_dependency")
            while True:
                page = desk_get(f"/tickets/{tid}/History", {"limit": 50, "from": frm}).get("data", [])
                for h in page:
                    for p in h.get("eventInfo") or []:
                        v = p.get("propertyValue")
                        if p.get("propertyName") == "Dependency" and isinstance(v, dict):
                            deps += [x for x in (v.get("previousValue"), v.get("updatedValue")) if x]
                        if p.get("propertyName") == "Tags" and isinstance(v, list):
                            tags |= set(v)
                if len(page) < 50:
                    break
                frm += 50
            return {"dependency": cur, "dependency_ever": sorted(set(deps + ([cur] if cur else []))),
                    "tags_now": sorted(tags_now), "tags_ever": sorted(tags)}
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def candidates():
    rca = json.loads((HERE / "rca.json").read_text())
    return [(r["ticket_id"], r["date"]) for r in rca["rows"] if r["state"] == "not_investigated" and r["dependency"] != "Warehouse"]


def main():
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    recent = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
    todo = [t for t, d in candidates() if t not in out or d >= recent]
    print(len(todo), "tickets to fetch")
    today = datetime.now(timezone.utc).date().isoformat()
    n = 0
    with ThreadPoolExecutor(5) as ex:
        for tn, res in zip(todo, ex.map(fetch_routing, todo)):
            n += 1
            if res:
                out[tn] = dict(res, fetched_on=today)
            if n % 50 == 0:
                OUT.write_text(json.dumps(out, separators=(",", ":")))
                print(n, "done", flush=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print("saved", len(out))


if __name__ == "__main__":
    main()
