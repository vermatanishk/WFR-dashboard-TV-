"""Reads the Warehouse-team Zoho comments of the swap-case tickets (build_swap.select_tickets) into
zoho_raw90/wh_text_check.json, same schema/rules as recheck_wh_comments.py (admitted/denied final, others re-read,
tickets younger than T-2 skipped, paired by ticketNumber). Run before build_swap.py."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from build_swap import HERE, select_tickets
from recheck_wh_comments import CACHE, IST, comments_for
from wh_comment_classifier import classify_wh_comments, investigation_subtype, strip_html

tickets, _ = select_tickets()
cap = json.loads((HERE / "rca.json").read_text())["t2_cap_date"]
cache = json.loads(CACHE.read_text())
todo = [t for t in tickets.values() if t["created"] <= cap and cache.get(t["ticket_id"], {}).get("verdict") not in ("admitted", "denied")]
print(len(todo), "to read")
today = datetime.now(IST).date().isoformat()
with ThreadPoolExecutor(5) as ex:
    for t, cm in zip(todo, ex.map(lambda t: comments_for(t["ticket_id"]), todo)):
        if cm is None:
            print("failed", t["ticket_id"]); continue
        res = classify_wh_comments(cm)
        wh = sorted([c for c in cm if ((c.get("commenter") or {}).get("roleName") or "").strip().lower().startswith("warehouse")], key=lambda c: c.get("commentedTime") or "")
        texts = [strip_html(c.get("content")) for c in wh]
        sub = next((x for x in reversed([investigation_subtype(x) for x in texts]) if x), None)
        cache[t["ticket_id"]] = {"admitted": res["verdict"] == "admitted", "order_id": t["order_id"], "reason": res["reason"], "wh_comment": res["evidence"],
                                 "verdict": res["verdict"], "evidence": res["evidence"], "rechecked_on": today, "subtype": sub, "wh_texts": [x[:160] for x in texts[:6]]}
CACHE.write_text(json.dumps(cache))
print("done")
