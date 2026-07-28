"""
Builds the Zoho EOD tab dataset: T-2 (the day before yesterday)'s mis-shipment
tickets only, classified WH-Accepted by the WAREHOUSE TEAM's own comment text -
not by category, and not by what the support agent/customer said.

Pull window is T-2, not T-1 ("yesterday"), per ops feedback: at the 5am run,
the Warehouse team often hasn't posted its comment on a T-1 ticket yet, so a
same-day/T-1 pull undercounts WH-Accepted just from comment-posting lag, not
an actual absence of admission. T-2 gives the WH team a full day to comment.

WH-Accepted (text) = a comment from a "Warehouse" role commenter on the
ticket contains a genuine ADMISSION (e.g. "we have sent wrong sku",
"we have sent short qty"). The common WH template "We have sent proper
medicine to Cx" is a DENIAL, not an admission, and does NOT count -
even though it's the same commenter/role, the content matters.
Support/L2-agent comments restating the customer's complaint (e.g.
"customer has received X instead of Y") never count - only the WH
team's own words do.

Location comes from marketplace_orders.warehouse_id directly (not the
return_request join used elsewhere), since same-day tickets usually
have no return record yet.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join
ORDER_LOCATION = {
    3037230: "Kolkata", 3120313: "Kolkata", 3120838: "Lucknow", 3147111: "Delhi",
    3142506: "Kolkata", 3164368: "Delhi", 3107816: "Delhi", 3171395: "Kolkata",
    3164189: "Bangalore", 3111787: "Bangalore", 3159511: "Bangalore",
    3145977: "Mumbai", 3136382: "Lucknow", 3106929: "Bangalore", 3156143: "Kolkata",
    3123162: "Bangalore", 2848423: "Mumbai", 3169351: "Delhi", 3151215: "Delhi",
    3132055: "Delhi", 3122871: "Delhi", 3151349: "Kolkata", 3141425: "Kolkata",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None/"" means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any).
WH_COMMENT = {
    "245052": "We have sent proper medicine to Cx",
    "245208": "We have sent proper medicine to Cx",
    "245481": "We have sent proper medicine to Cx",
    "245827": "We have sent proper medicine to Cx",
    "245834": "We have sent proper medicine to Cx",
    "245111": "We have sent proper medicine to Cx",
    "245735": "We have sent proper medicine to Cx",
    "245871": "We have sent proper medicine to Cx",
    "245189": "We have sent proper medicine to Cx",
    "245198": "We have sent proper medicine to Cx",
    "245897": "We have sent proper medicine to Cx",
    "245197": "We have sent proper medicine to Cx",
    "245485": None,
    "246023": "We have sent proper medicine to Cx",
    "245804": "We have sent wrong sku to Cx",
    "245161": "We have sent proper medicine to Cx",
    "245206": "We have sent wrong sku to Cx",
    "245689": None,
    "245877": "We have sent proper medicine to cx",
    "245124": None,
    "245199": None,
    "245756": None,
    "245213": None,
    "245739": None,
    "245732": None,
}

TICKETS = [
    {"ticket_id": "245052", "order_id": 3037230, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T03:21:27"},
    {"ticket_id": "245208", "order_id": 3120313, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T07:32:29"},
    {"ticket_id": "245481", "order_id": 3120838, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T07:56:57"},
    {"ticket_id": "245827", "order_id": 3147111, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T11:47:40"},
    {"ticket_id": "245834", "order_id": 3142506, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T12:01:49"},
    {"ticket_id": "245111", "order_id": 3164368, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T04:59:36"},
    {"ticket_id": "245735", "order_id": 3107816, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T09:22:26"},
    {"ticket_id": "245871", "order_id": 3171395, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T13:11:31"},
    {"ticket_id": "245189", "order_id": 3164189, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T07:14:35"},
    {"ticket_id": "245198", "order_id": 3111787, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T07:21:09"},
    {"ticket_id": "245897", "order_id": 3159511, "category": "Missing/Wrong Qty", "created_time": "2026-07-26T13:50:07"},
    {"ticket_id": "245197", "order_id": 3145977, "category": "Wrong Medicines", "created_time": "2026-07-26T07:18:39"},
    {"ticket_id": "245485", "order_id": 3136382, "category": "Wrong Medicines", "created_time": "2026-07-26T07:57:01"},
    {"ticket_id": "246023", "order_id": 3037230, "category": "Wrong Medicines", "created_time": "2026-07-26T14:21:12"},
    {"ticket_id": "245804", "order_id": 3106929, "category": "Wrong Medicines", "created_time": "2026-07-26T11:02:47"},
    {"ticket_id": "245161", "order_id": 3156143, "category": "Wrong Medicines", "created_time": "2026-07-26T06:23:50"},
    {"ticket_id": "245206", "order_id": 3123162, "category": "Wrong Medicines", "created_time": "2026-07-26T07:28:39"},
    {"ticket_id": "245689", "order_id": 2848423, "category": "Damaged/Defective", "created_time": "2026-07-26T08:16:11"},
    {"ticket_id": "245877", "order_id": 3169351, "category": "Damaged/Defective", "created_time": "2026-07-26T13:22:09"},
    {"ticket_id": "245124", "order_id": 3151215, "category": "Damaged/Defective", "created_time": "2026-07-26T05:24:09"},
    {"ticket_id": "245199", "order_id": 3132055, "category": "Damaged/Defective", "created_time": "2026-07-26T07:22:45"},
    {"ticket_id": "245756", "order_id": 3122871, "category": "Damaged/Defective", "created_time": "2026-07-26T10:02:43"},
    {"ticket_id": "245213", "order_id": 3151349, "category": "Damaged/Defective", "created_time": "2026-07-26T07:38:32"},
    {"ticket_id": "245739", "order_id": 3141425, "category": "Damaged/Defective", "created_time": "2026-07-26T09:35:52"},
    {"ticket_id": "245732", "order_id": 3141425, "category": "Damaged/Defective", "created_time": "2026-07-26T09:21:23"},
]

# Genuine admission phrases the WH team uses when they DO own the mistake.
# "we have sent proper medicine" / "correct item" etc. are denials and never match.
ADMISSION_PHRASES = ["wrong sku", "wrong item", "wrong qty", "wrong medicine",
                      "short qty", "less qty", "sent short", "sent wrong", "missing qty"]


def classify(wh_comment):
    if not wh_comment:
        return False, "No Warehouse-team comment on this ticket - not counted (need an explicit WH admission, not silence)."
    low = wh_comment.lower()
    if any(p in low for p in ADMISSION_PHRASES):
        return True, f"Warehouse team comment: \"{wh_comment}\" - explicit admission, counted WH-Accepted."
    return False, f"Warehouse team comment: \"{wh_comment}\" - this is a denial (WH says they sent the correct item), not an admission. Not counted."


out_tickets = []
for t in TICKETS:
    wh_comment = WH_COMMENT.get(t["ticket_id"])
    wh_accepted, reason = classify(wh_comment)
    out_tickets.append({
        **t,
        "location": ORDER_LOCATION.get(t["order_id"], "Unknown"),
        "wh_comment": wh_comment,
        "wh_accepted_text": wh_accepted,
        "reason": reason,
    })

eod_data = {
    "generated_at": "2026-07-28T13:41:07Z",
    "for_date": "2026-07-26",
    "methodology": "WH-Accepted here is TEXT-BASED and requires the Warehouse team's OWN comment (Zoho commenter role 'Warehouse') to contain a genuine admission (e.g. 'we have sent wrong sku', 'short qty') - not the support agent's restatement of the customer's complaint, and not the WH team's stock denial ('We have sent proper medicine to Cx'). This is stricter than category alone, so it undercounts relative to the eventual ClickHouse-confirmed return outcome, but gives ops a same-day, defensible WH-admission signal rather than a proxy.",
    "tickets": out_tickets,
}
(HERE / "data_eod.json").write_text(json.dumps(eod_data, indent=2))

total = len(out_tickets)
accepted = sum(1 for t in out_tickets if t["wh_accepted_text"])
by_cat = defaultdict(lambda: {"total": 0, "accepted": 0})
by_loc = defaultdict(lambda: {"total": 0, "accepted": 0})
for t in out_tickets:
    by_cat[t["category"]]["total"] += 1
    by_loc[t["location"]]["total"] += 1
    if t["wh_accepted_text"]:
        by_cat[t["category"]]["accepted"] += 1
        by_loc[t["location"]]["accepted"] += 1

print(f"Total: {total}, WH-Accepted (text): {accepted} ({round(100*accepted/total,1)}%)")
print("By category:", dict(by_cat))
print("By location:", dict(by_loc))
