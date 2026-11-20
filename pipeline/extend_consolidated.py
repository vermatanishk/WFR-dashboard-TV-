"""Make sure NO ticket is missed: add to zoho_raw90/consolidated.json every Zoho REST ticket (cmp_zoho_tickets.json, all dispositions, pulled by
pull_complaint_tickets.py) that maps to one of the 5 dashboard categories and is not there yet. Existing rows are never changed or removed.
Switch Orders / MRP are excluded exactly like the original pull. Prints the order ids that still need ClickHouse joins (returns / pickers / QC /
cold flag) - pull them into the next ch_*_cN chunk (see CLAUDE.md)."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from category_mapping import normalize
cons_p = HERE / "zoho_raw90/consolidated.json"
cons = json.loads(cons_p.read_text())
have = {x["ticket_id"] for x in cons}
days = json.loads((HERE / "zoho_raw90/cmp_zoho_tickets.json").read_text())["days"]
add = []
for d, l in sorted(days.items()):
    for t in l:
        cat = normalize(t["sub_disposition"])
        if cat and cat != "Switch Orders" and not cat.startswith("MRP") and t["ticket_id"] not in have:
            add.append({"ticket_id": t["ticket_id"], "order_id": t["order_raw"] if t["order_raw"] not in (None, "unparseable") else "",
                        "sub_disposition": t["sub_disposition"], "created_time": t["created_time"], "status": t["status"], "channel": t["channel"],
                        "department": "Support", "assignee": None, "category": cat})
if add:
    cons += add
    cons.sort(key=lambda x: x["created_time"])
    cons_p.write_text(json.dumps(cons))
print(f"consolidated: {len(cons)} tickets, added {len(add)}", [a["ticket_id"] for a in add][:20])
def po(raw):
    s = str(raw or "").strip().rstrip(".")
    return int(s) if s.isdigit() and 10**5 <= int(s) <= 10**9 else None
known = set()
for p in (HERE / "zoho_raw90").glob("ch_qc_c*.jsonl"):
    known |= {json.loads(l)["order_id"] for l in open(p) if l.strip()}
retk = set()
for p in (HERE / "zoho_raw90").glob("ch_returns_c*.jsonl"):
    retk |= {json.loads(l)["order_id"] for l in open(p) if l.strip()}
cold = json.loads((HERE / "order_cold_flag.json").read_text())
need = sorted({po(a["order_id"]) for a in add if po(a["order_id"])} | {po(x["order_id"]) for x in cons if x["created_time"][:10] >= sys.argv[1] and po(x["order_id"]) and po(x["order_id"]) not in known and str(po(x["order_id"])) not in cold} if len(sys.argv) > 1 else {po(a["order_id"]) for a in add if po(a["order_id"])})
print("orders needing ClickHouse joins:", len(need), ",".join(map(str, need)))
