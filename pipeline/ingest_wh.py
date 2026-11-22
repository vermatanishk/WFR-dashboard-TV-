"""
Ingest Warehouse-role Zoho comments that were read through the Zoho Desk MCP (REST unavailable) into wh_text_check.json,
using the SAME classifier as recheck_wh_comments.py (never a hand verdict).

  python3 pipeline/ingest_wh.py <file.json>
file.json = {"<ticketNumber>": [["<ISO commentedTime>", "<Warehouse comment text>"], ...]}   ([] = ticket read, no Warehouse comment)
Only Warehouse-role comments are needed (other roles never influence the verdict). Pairing is by ticketNumber, as always.
`admitted` is never downgraded; provisional verdicts are overwritten; order_id comes from data.json / cmp_zoho_tickets when known.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wh_comment_classifier import classify_wh_comments, investigation_subtype

HERE = Path(__file__).parent
CACHE = HERE / "zoho_raw90/wh_text_check.json"
IST = timezone(timedelta(hours=5, minutes=30))


def main(path):
    cache = json.loads(CACHE.read_text())
    data = json.loads(Path(path).read_text())
    order = {str(t["ticket_id"]): t["order_id"] for t in json.loads((HERE / "data.json").read_text())["tickets"]}
    today = datetime.now(IST).date().isoformat()
    out = {}
    for tn, wh in data.items():
        comments = [{"content": f"<div>{txt}</div>", "commentedTime": ts, "commenter": {"roleName": "Warehouse "}} for ts, txt in wh]
        res = classify_wh_comments(comments)
        old = cache.get(tn, {}).get("verdict")
        if old == "admitted" and res["verdict"] != "admitted":
            print(tn, "kept admitted (re-read said", res["verdict"] + ")")
            continue
        rec = {"verdict": res["verdict"], "evidence": res.get("evidence"), "reason": res.get("reason"),
               "order_id": order.get(tn, cache.get(tn, {}).get("order_id")), "admitted": res["verdict"] == "admitted",
               "rechecked_on": today, "wh_texts": [t for _, t in wh], "source": "zoho-mcp"}
        try:
            rec["subtype"] = investigation_subtype([c for c in comments]) if callable(investigation_subtype) else None
        except Exception:
            pass
        cache[tn] = rec
        out[tn] = res["verdict"]
    CACHE.write_text(json.dumps(cache))
    print(len(out), "tickets written:", dict(sorted(((v, list(out.values()).count(v)) for v in set(out.values())))))
    for tn, v in out.items():
        print(" ", tn, v)


if __name__ == "__main__":
    main(sys.argv[1])
