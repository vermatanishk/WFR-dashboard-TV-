"""
Re-reads Warehouse-team Zoho comments live and (re)writes zoho_raw90/wh_text_check.json for
every ticket whose verdict is NOT final:
  - cached `no_wh_comment` / `unrecognized` (provisional: WH often comments after the first read -
    found 2026-10-14: 233123 and 250676 both had a WH comment but were cached as no_wh_comment), and
  - tickets with no cache entry yet.
`admitted` / `denied` are final and never re-read (CLAUDE.md rule). Tickets younger than T-2 are
left alone (WH has not had time to comment; never cache a verdict for them).

Pairing is by ticketNumber from searchTickets (one ticket per call), never by position.
Auth: pipeline/zoho_auth.py (REST); fall back to the Zoho Desk MCP getTicketComments if it fails.

Run: python3 pipeline/recheck_wh_comments.py [--limit N] [--extra zoho_raw90/cmp_tickets_to_read.json]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wh_comment_classifier import classify_wh_comments, investigation_subtype, strip_html
from zoho_auth import desk_get, get_token

HERE = Path(__file__).parent
CACHE = HERE / "zoho_raw90/wh_text_check.json"
IST = timezone(timedelta(hours=5, minutes=30))


def comments_for(ticket_number, tries=4):
    for i in range(tries):
        try:
            rows = desk_get("/tickets/search", {"ticketNumber": ticket_number, "limit": 1}).get("data") or []
            hit = next((r for r in rows if str(r.get("ticketNumber")) == str(ticket_number)), None)
            if not hit:
                return None
            out, frm = [], 1
            while True:
                page = desk_get(f"/tickets/{hit['id']}/comments", {"limit": 100, "from": frm}).get("data") or []
                out += page
                if len(page) < 100:
                    break
                frm += 100
            return out
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    get_token()
    data = json.loads((HERE / "data.json").read_text())
    cap = (datetime.strptime(data["generated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
           .astimezone(IST) - timedelta(days=2)).date().isoformat()
    cache = json.loads(CACHE.read_text())
    todo = []
    for t in data["tickets"]:
        tid = t["ticket_id"]
        if t["created_time"][:10] > cap:
            continue
        if tid not in cache or cache[tid].get("verdict") in ("no_wh_comment", "unrecognized"):
            todo.append(t)
    if "--extra" in sys.argv:        # complaint-baseline tickets outside data.json (build_complaints.py -> cmp_tickets_to_read.json)
        seen = {t["ticket_id"] for t in todo}
        cap = (datetime.now(IST) - timedelta(days=2)).date().isoformat()     # baseline tickets are read against TODAY's T-2, not data.json's
        for t in json.loads(Path(sys.argv[sys.argv.index("--extra") + 1]).read_text()):
            tid = t["ticket_id"]
            if tid in seen or t["created_time"][:10] > cap:
                continue
            if tid not in cache or cache[tid].get("verdict") in ("no_wh_comment", "unrecognized"):
                todo.append(t)
                seen.add(tid)
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} tickets to (re)read; T-2 cap {cap}")
    changed = failed = n = 0
    today = datetime.now(IST).date().isoformat()

    def work(t):
        return t, comments_for(t["ticket_id"])

    with ThreadPoolExecutor(6) as ex:
        for t, cm in ex.map(work, todo):
            n += 1
            if cm is None:
                failed += 1
                continue
            res = classify_wh_comments(cm)
            # why it could not be investigated, read from EVERY Warehouse comment (a thread of
            # neutral 'Footage not found' notes has no admission/denial evidence to derive it from)
            wh = sorted([c for c in cm if ((c.get("commenter") or {}).get("roleName") or "").strip().lower().startswith("warehouse")],
                        key=lambda c: c.get("commentedTime") or "")
            texts = [strip_html(c.get("content")) for c in wh]
            subs = [investigation_subtype(x) for x in texts]
            sub = next((x for x in reversed(subs) if x), None)
            old = cache.get(t["ticket_id"], {}).get("verdict")
            if res["verdict"] != old:
                changed += 1
            cache[t["ticket_id"]] = {
                "admitted": res["verdict"] == "admitted", "order_id": t["order_id"],
                "reason": res["reason"], "wh_comment": res["evidence"], "verdict": res["verdict"],
                "evidence": res["evidence"], "rechecked_on": today,
                "subtype": sub, "wh_texts": [x[:160] for x in texts[:6]],
            }
            if n % 100 == 0:
                CACHE.write_text(json.dumps(cache))
                print(f"  {n}/{len(todo)} read, {changed} changed, {failed} failed", flush=True)
    CACHE.write_text(json.dumps(cache))
    print(f"done: {n} read, {changed} verdicts changed, {failed} failed (use the MCP for those)")


if __name__ == "__main__":
    main()
