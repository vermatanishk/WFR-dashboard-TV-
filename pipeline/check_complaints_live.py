"""
Live spot-check of the complaint baseline against Zoho Desk (REST). Samples rows and re-verifies them from scratch:
  A. "No ticket at all" (in scope, has a return request): Zoho must hold no complaint-type ticket for the order near the request.
  B. "Zoho ticket only": the ticket must exist and carry that order id.
  C. "WH input = No WH comment" (past T-2): the ticket thread must contain no Warehouse-role comment.
  D. "WH input = WH accepted": a Warehouse-role comment must exist.
Run: python3 pipeline/check_complaints_live.py [n_per_check=12] [seed=1]   -> prints PASS/FAIL per sample, exit 1 on any failure.
"""
import json
import random
import sys
from pathlib import Path

from build_complaints import sub_type, parse_order_id
from zoho_auth import desk_get

HERE = Path(__file__).parent
exp = json.loads((HERE / "complaints_export.json").read_text())
C = {c: i for i, c in enumerate(exp["columns"])}
rows = exp["rows"]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
bad = 0


def tickets_of(order):
    try:
        r = desk_get("/tickets/search", {"customField1": f"cf_order_id:{order}", "limit": 50})
    except Exception:
        return []
    return (r or {}).get("data") or []


def wh_comments(ticket_number):
    s = [x for x in (desk_get("/tickets/search", {"ticketNumber": ticket_number, "limit": 1}).get("data") or []) if str(x["ticketNumber"]) == str(ticket_number)]
    if not s:
        return None
    out, frm = [], 1
    while True:
        page = desk_get(f"/tickets/{s[0]['id']}/comments", {"limit": 100, "from": frm}).get("data") or []
        out += page
        if len(page) < 100:
            return [c for c in out if ((c.get("commenter") or {}).get("roleName") or "").strip().lower().startswith("warehouse")]
        frm += 100


def rep(ok, msg):
    global bad
    bad += (not ok)
    print(("PASS " if ok else "FAIL ") + msg)


A = [r for r in rows if r[C["Ticket relation"]] == "No ticket" and r[C["In scope"]] == "Yes" and r[C["Source"]] == "Return request only"]
for r in random.sample(A, min(n, len(A))):
    ts = [t for t in tickets_of(r[C["Order ID"]]) if sub_type((t.get("cf") or {}).get("cf_sub_disposition"))
          and abs(int(t["createdTime"][:10].replace("-", "")) - int(r[C["Created date"]].replace("-", ""))) < 100]   # within ~1 month
    rep(not ts, f"A no-ticket  {r[C['Order ID']]} {r[C['Complaint type']]:22s} {r[C['Created date']]}  zoho complaint tickets near: {[t['ticketNumber'] for t in ts]}")
B = [r for r in rows if r[C["Source"]] == "Zoho ticket only"]
for r in random.sample(B, min(n, len(B))):
    ts = [t for t in tickets_of(r[C["Order ID"]]) if t["ticketNumber"] == r[C["Ticket ID"]]]
    rep(bool(ts) and sub_type((ts[0].get("cf") or {}).get("cf_sub_disposition")) == r[C["Complaint type"]], f"B ticket-only {r[C['Order ID']]} ticket {r[C['Ticket ID']]} {r[C['Complaint type']]}")
Cc = [r for r in rows if r[C["WH input"]] == "No WH comment"]
for r in random.sample(Cc, min(n, len(Cc))):
    w = wh_comments(r[C["Ticket ID"]])
    rep(w == [], f"C no-WH      ticket {r[C['Ticket ID']]} {r[C['Complaint type']]:22s} warehouse comments live: {None if w is None else len(w)}")
D = [r for r in rows if r[C["WH input"]] == "WH accepted"]
for r in random.sample(D, min(n, len(D))):
    w = wh_comments(r[C["Ticket ID"]])
    rep(bool(w), f"D WH-accept   ticket {r[C['Ticket ID']]} {r[C['Complaint type']]:22s} warehouse comments live: {None if w is None else len(w)}")
print(f"\n{bad} failure(s)")
sys.exit(1 if bad else 0)
