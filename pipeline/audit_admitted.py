"""Audit: re-read every ADMITTED verdict of the last 60 days live from Zoho REST (paired by ticketNumber) and compare with the cached one.
Prints disagreements (admission not found on the live thread = mis-paired / deleted comment); with --fix downgrades those to the live verdict.
usage: python3 pipeline/audit_admitted.py [--fix]"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from recheck_wh_comments import comments_for
from wh_comment_classifier import classify_wh_comments, strip_html
HERE = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
cache = json.loads((HERE / "zoho_raw90/wh_text_check.json").read_text())
data = json.loads((HERE / "data.json").read_text())
cut = (datetime.now(IST).date() - timedelta(days=60)).isoformat()
ids = [t["ticket_id"] for t in data["tickets"] if t["created_time"][:10] >= cut and (cache.get(t["ticket_id"]) or {}).get("verdict") == "admitted"]
ex = HERE / "zoho_raw90/cmp_tickets_to_read.json"
if ex.exists():
    ids += [t["ticket_id"] for t in json.loads(ex.read_text()) if t["created_time"][:10] >= cut and (cache.get(t["ticket_id"]) or {}).get("verdict") == "admitted" and t["ticket_id"] not in ids]
print(len(ids), "admitted tickets to audit")
bad = []
with ThreadPoolExecutor(6) as exr:
    for tid, cm in zip(ids, exr.map(comments_for, ids)):
        if cm is None:
            print("could not read", tid); continue
        res = classify_wh_comments(cm)
        if res["verdict"] != "admitted":
            bad.append((tid, res["verdict"], (cache[tid].get("evidence") or "")[:70], (res.get("evidence") or "")[:70]))
            if "--fix" in sys.argv:
                cache[tid].update({"verdict": res["verdict"], "admitted": False, "evidence": res["evidence"], "wh_comment": res["evidence"], "reason": res["reason"]})
print(len(bad), "disagreements"); [print(b) for b in bad]
if "--fix" in sys.argv:
    (HERE / "zoho_raw90/wh_text_check.json").write_text(json.dumps(cache))
