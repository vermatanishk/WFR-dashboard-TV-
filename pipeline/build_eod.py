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
have no return record yet. CRITICAL: marketplace_orders has TWO id
columns - "id" (internal PK) and "order_id" (the customer-facing
number used everywhere else - Zoho tickets, marketplace_order_status_
log, warehouse_warehouse_scan_log). The join MUST be on order_id, not
id - joining on id silently returns the wrong warehouse (or Unknown)
for most orders, since the two numbers diverge. This caused every
location in this tab to be wrong or Unknown until 2026-08-01; always
verify the join column name explicitly before trusting a location.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join
ORDER_LOCATION = {
    3246347: "Bangalore", 3242929: "Delhi", 3240712: "Mumbai", 3241917: "Kolkata",
    3248204: "Bangalore", 3223227: "Delhi", 3234383: "Delhi", 3214541: "Bangalore",
    3235104: "Bangalore", 3231814: "Bangalore", 3239875: "Bangalore", 3222307: "Delhi",
    3231210: "Lucknow", 3211157: "Delhi",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None/"" means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any).
WH_COMMENT = {
    "250509": None,
    "250480": "We have sent proper medicine to Cx",
    "250482": "We have sent proper medicine to Cx",
    "250458": "We have sent proper medicine to Cx",
    "250489": "We have sent proper medicine to Cx",
    "250479": "We have sent proper medicine to Cx",
    "250432": "We have sent proper medicine to Cx",
    "250491": "We have sent proper medicine to Cx",
    "250487": "We have sent proper medicine to Cx",
    "250488": "We have sent proper medicine to Cx",
    "250476": "We have sent proper medicine to Cx",
    "250405": None,
    "250494": "We have sent proper medicine to Cx",
    "250454": "We have sent wrong sku to Cx",
}

TICKETS = [
    {"ticket_id": "250509", "order_id": 3246347, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T13:35:29"},
    {"ticket_id": "250480", "order_id": 3242929, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T10:47:53"},
    {"ticket_id": "250482", "order_id": 3240712, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T10:52:44"},
    {"ticket_id": "250458", "order_id": 3241917, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T08:47:56"},
    {"ticket_id": "250489", "order_id": 3248204, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T11:47:59"},
    {"ticket_id": "250479", "order_id": 3223227, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T10:45:08"},
    {"ticket_id": "250432", "order_id": 3234383, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T06:50:04"},
    {"ticket_id": "250491", "order_id": 3214541, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T11:54:01"},
    {"ticket_id": "250487", "order_id": 3235104, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T11:43:10"},
    {"ticket_id": "250488", "order_id": 3231814, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T11:44:15"},
    {"ticket_id": "250476", "order_id": 3239875, "category": "Missing/Wrong Qty", "created_time": "2026-08-02T10:35:16"},
    {"ticket_id": "250405", "order_id": 3222307, "category": "Wrong Medicines", "created_time": "2026-08-02T04:52:29"},
    {"ticket_id": "250494", "order_id": 3231210, "category": "Wrong Medicines", "created_time": "2026-08-02T12:04:48"},
    {"ticket_id": "250454", "order_id": 3211157, "category": "Wrong Medicines", "created_time": "2026-08-02T08:39:09"},
]

# Genuine admission phrases the WH team uses when they DO own the mistake.
# "we have sent proper medicine" / "correct item" etc. are denials and never match.
#
# WARNING (confirmed false-positive, 2026-08-01, ticket 248136): naive substring
# matching is not enough. The WH comment "Kindly share the image of wrong
# medicine Because it helpfull to find" matched "wrong medicine" and was
# wrongly counted WH-Accepted - it's the WH team ASKING for photo evidence,
# not admitting fault. classify() below is a simplified reference impl for
# offline/manual runs only; when the live routine (an LLM reading real
# comment text) applies this list, it MUST read the full sentence for intent
# - a request for evidence, a question, or someone else's restatement is NOT
# an admission even if it contains a matching phrase. Only count a first-
# person WH statement of fact about what THEY did ("we sent/dispatched
# wrong/short X").
ADMISSION_PHRASES = ["wrong sku", "wrong item", "wrong qty", "wrong medicine",
                      "short qty", "less qty", "sent short", "sent wrong", "missing qty"]

# Full fulfilment-chain attribution for WH-Accepted (text) tickets only, from
# ClickHouse, joined by order_id - independent of the ClickHouse return-request
# resolution, since a T-2 order usually has no return record yet. Only
# populated for tickets where wh_accepted_text is True - not-counted tickets
# don't need attribution. Sources (all FINAL + _peerdb_is_deleted=0):
#   picker     - warehouse_warehouse_scan_log, scanner(s) with the most picks
#                on that order (ties shown as "A / B")
#   packer     - marketplace_order_status_log, ops_user_name at
#                current_status_id=52 ("pharmacistAccepted")
#   qc         - marketplace_order_status_log, ops_user_name at
#                current_status_id=61 ("packedAndQCed")
#   manifester - marketplace_order_status_log, ops_user_name at
#                current_status_id=64 ("manifested")
PICKER_QC = {
    "250454": {"picker": "Sabrin_DEL", "packer": "Minzar_DEL", "qc": "Shailesh_DEL", "manifester": "Ruksana_DEL"},
}


# Request-for-evidence phrasing that can contain admission-sounding words
# without being an admission (see WARNING above re: ticket 248136).
REQUEST_PHRASES = ["kindly share", "please share", "share the image", "share image",
                    "share the photo", "share photo", "send the image", "send image",
                    "send the photo", "send photo", "provide image", "provide photo",
                    "helpfull to find", "helpful to find"]


def classify(wh_comment):
    if not wh_comment:
        return False, "No Warehouse-team comment on this ticket - not counted (need an explicit WH admission, not silence)."
    low = wh_comment.lower()
    if any(p in low for p in REQUEST_PHRASES):
        return False, f"Warehouse team comment: \"{wh_comment}\" - this is a REQUEST for evidence, not an admission (an admission phrase may appear as a substring, but the sentence isn't a first-person statement of fault). Not counted."
    if any(p in low for p in ADMISSION_PHRASES):
        return True, f"Warehouse team comment: \"{wh_comment}\" - explicit admission, counted WH-Accepted."
    return False, f"Warehouse team comment: \"{wh_comment}\" - this is a denial (WH says they sent the correct item), not an admission. Not counted."


out_tickets = []
for t in TICKETS:
    wh_comment = WH_COMMENT.get(t["ticket_id"])
    wh_accepted, reason = classify(wh_comment)
    pq = PICKER_QC.get(t["ticket_id"], {}) if wh_accepted else {}
    out_tickets.append({
        **t,
        "location": ORDER_LOCATION.get(t["order_id"], "Unknown"),
        "wh_comment": wh_comment,
        "wh_accepted_text": wh_accepted,
        "reason": reason,
        "picker": pq.get("picker"),
        "packer": pq.get("packer"),
        "qc": pq.get("qc"),
        "manifester": pq.get("manifester"),
    })

eod_data = {
    "generated_at": "2026-08-03T21:28:39Z",
    "for_date": "2026-08-02",
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
