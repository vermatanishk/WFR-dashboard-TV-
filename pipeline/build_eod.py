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
    3139834: "Bangalore", 3199760: "Bangalore", 3239286: "Kolkata", 3282854: "Kolkata",
    3305533: "Kolkata", 3306311: "Delhi", 3309959: "Delhi", 3315632: "Mumbai",
    3321270: "Delhi", 3321729: "Bangalore", 3322445: "Lucknow", 3323274: "Lucknow",
    3326482: "Delhi", 3327261: "Delhi", 3333178: "Bangalore", 3334231: "Bangalore",
    3337963: "Bangalore", 3340056: "Delhi", 3341591: "Delhi", 3341818: "Mumbai",
    3344321: "Kolkata", 3347474: "Delhi", 3356833: "Delhi", 3358216: "Mumbai",
    3359927: "Delhi", 3368432: "Lucknow", 3369390: "Delhi", 3131834: "Delhi",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None/"" means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any).
WH_COMMENT = {
    "251973": "We have sent proper medicine to Cx",
    "251961": "We have sent proper medicine to cx",
    "251960": "We have sent proper medicine to cx",
    "251945": "We have sent proper medicine to cx",
    "251953": "We have sent proper medicine to Cx",
    "251984": "We have sent proper medicine to Cx",
    "251939": "We have sent short qty to cx",
    "251947": "we have sent proper medicine to cx",
    "251874": "We have sent proper medicine to Cx",
    "251937": "We have sent proper medicine to cx",
    "251951": "We have sent proper medicine to Cx",
    "251930": "We have sent proper medicine to cx",
    "251938": None,
    "251923": "Footage not found because cctv under Maintenance",
    "251920": "We have sent proper medicine to Cx",
    "251918": "We have sent proper medicine to cx",
    "251882": None,
    "251832": "We have sent proper medicine to cx",
    "251859": None,
    "251839": "We have sent proper medicine to cx",
    "251964": "This batch is not available in our inventory",
    "251936": "We have sent proper medicine to cx",
    "251934": "We have sent wrong medicine to cx",
    "251831": "We have sent wrong medicine to cx",
    "251890": "We have sent proper medicine to Cx",
    "251888": None,
    "251866": None,
    "251828": None,
}

TICKETS = [
    {"ticket_id": "251973", "order_id": 3337963, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T12:47:41"},
    {"ticket_id": "251961", "order_id": 3321270, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T12:25:51"},
    {"ticket_id": "251960", "order_id": 3333178, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T12:18:22"},
    {"ticket_id": "251945", "order_id": 3321729, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:31:28"},
    {"ticket_id": "251953", "order_id": 3356833, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T12:01:25"},
    {"ticket_id": "251984", "order_id": 3359927, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T13:25:33"},
    {"ticket_id": "251939", "order_id": 3305533, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:16:44"},
    {"ticket_id": "251947", "order_id": 3334231, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:33:19"},
    {"ticket_id": "251874", "order_id": 3358216, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T06:49:26"},
    {"ticket_id": "251937", "order_id": 3368432, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:10:24"},
    {"ticket_id": "251951", "order_id": 3282854, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:46:52"},
    {"ticket_id": "251930", "order_id": 3306311, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T10:45:14"},
    {"ticket_id": "251938", "order_id": 3239286, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T11:11:04"},
    {"ticket_id": "251923", "order_id": 3344321, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T10:25:06"},
    {"ticket_id": "251920", "order_id": 3315632, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T10:21:45"},
    {"ticket_id": "251918", "order_id": 3326482, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T10:16:47"},
    {"ticket_id": "251882", "order_id": 3347474, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T07:33:45"},
    {"ticket_id": "251832", "order_id": 3139834, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T04:44:55"},
    {"ticket_id": "251859", "order_id": 3199760, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T06:08:03"},
    {"ticket_id": "251839", "order_id": 3323274, "category": "Missing/Wrong Qty", "created_time": "2026-08-10T04:57:30"},
    {"ticket_id": "251964", "order_id": 3341818, "category": "Wrong Medicines", "created_time": "2026-08-10T12:29:16"},
    {"ticket_id": "251936", "order_id": 3340056, "category": "Wrong Medicines", "created_time": "2026-08-10T11:08:28"},
    {"ticket_id": "251934", "order_id": 3309959, "category": "Wrong Medicines", "created_time": "2026-08-10T11:05:38"},
    {"ticket_id": "251831", "order_id": 3327261, "category": "Wrong Medicines", "created_time": "2026-08-10T04:43:41"},
    {"ticket_id": "251890", "order_id": 3322445, "category": "Damaged/Defective", "created_time": "2026-08-10T07:55:21"},
    {"ticket_id": "251888", "order_id": 3369390, "category": "Damaged/Defective", "created_time": "2026-08-10T07:53:41"},
    {"ticket_id": "251866", "order_id": 3341591, "category": "Damaged/Defective", "created_time": "2026-08-10T06:17:24"},
    {"ticket_id": "251828", "order_id": 3131834, "category": "Damaged/Defective", "created_time": "2026-08-10T04:20:50"},
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
#   picker     - warehouse_warehouse_scan_log (JSONExtractInt(metadata,'orderId') = order_id), grouped by scanned_by_user_id, taking the user_id(s) with the MAX pick count (ties -> join names with " / ", same tie rule as build_full_dataset.py's picker_str()). Resolve user_id to name via pipeline/zoho_raw90/user_names.json (from step 3) or a fresh auth_internal_users lookup if missing.
#   packer     - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 52 ("pharmacistAccepted") - ops_user_name is already the display name, use directly.
#   qc (checker) - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 61 ("packedAndQCed") - same as before, unchanged.
#   manifester - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 64 ("manifested") - ops_user_name is the display name, use directly.
PICKER_QC = {
    "251939": {"picker": "Priyanka_KOL / Rakeshkayal_KOL", "packer": "Priyanka_KOL", "qc": "Surojit_KOL", "manifester": "Biswajit_KOL"},
    "251934": {"picker": "Roshan_P-DEL", "packer": "Durgesh_DEL", "qc": "Shailesh_DEL", "manifester": "Ronu_DEL"},
    "251831": {"picker": "Sanjay_v_DEL", "packer": "Kuldeep_Del", "qc": "Devki-DEL", "manifester": "Ronu_DEL"},
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
    return False, f"Warehouse team comment: \"{wh_comment}\" - this is a denial or non-admission (does not state WH sent the wrong/short item), not an admission. Not counted."


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
    "generated_at": "2026-08-12T17:30:00Z",
    "for_date": "2026-08-10",
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
