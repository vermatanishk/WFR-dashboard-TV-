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

2026-08-13 run note: verified the marketplace_orders/marketplace_warehouses
join by spot-checking packer usernames against warehouse_name city suffixes
(_BLRWH=Bangalore, _MUM=Mumbai, _LKO=Lucknow) for all 4 WH-Accepted orders -
all 4 matched, join is correct.

2026-08-13 run note: ticket 252177 (Wrong Medicines) has a null Order ID in
Zoho (customer never got an order number confirmed/linked), so it has no
ClickHouse location and is excluded from location-join lookups; it still
counts in the tickets total. No Warehouse-team comment was posted on it
either (only L2 "spoke to user, will share image" notes), so it doesn't
affect WH-Accepted count.

2026-08-13 run note: ticket 252210 is a genuine WH admission ("We have sent
cerecetam syrup 1 qty short to Cx") but the L2 comment posted afterward reads
"Return pickup initiated and BOD issued for the missing quantity" - i.e. the
support-side system also logged a BOD action on the same ticket. Per the
methodology, wh_accepted_text stays True (it's driven by the WH admission
text, not the later L2/BOD note) - this is a known, currently-unresolved
discrepancy between the two systems' bookkeeping, not a classification bug.
Same pattern as ticket 251580 noted in an earlier run.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join (on order_id,
# NOT the internal "id" column - see docstring above).
ORDER_LOCATION = {
    3383809: "Bangalore", 3351910: "Lucknow", 3280391: "Kolkata", 3349841: "Lucknow",
    3338561: "Kolkata", 3331716: "Bangalore", 3352948: "Delhi", 3341342: "Bangalore",
    3312631: "Lucknow", 3311178: "Bangalore", 3351721: "Delhi", 3183944: "Bangalore",
    3370292: "Delhi", 3385467: "Delhi", 3342441: "Delhi", 3319912: "Bangalore",
    3225380: "Lucknow", 3342175: "Bangalore", 3377556: "Kolkata", 3331405: "Lucknow",
    3309457: "Mumbai", 3236098: "Bangalore", 3304901: "Delhi", 3322180: "Delhi",
    3287652: "Delhi", 3343936: "Mumbai",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any) -
# confirmed by reading the FULL comment list for every ticket, not just the latest.
WH_COMMENT = {
    "252224": "We have sent proper medicine to Cx",
    "252157": "We have sent proper medicine to Cx",
    "252041": "We have sent proper medicine to Cx",
    "252219": "We have sent short qty to Cx",
    "252196": "Footage not found because it is under maintenance",
    "252210": "We have sent cerecetam syrup 1 qty short to Cx",
    "252167": "We have sent proper medicine to Cx",
    "252193": "We have sent proper medicine to Cx",
    "252212": "We have sent proper medicine to Cx",
    "252213": "We have sent proper medicine to Cx",
    "252130": "We have sent proper medicine to Cx",
    "252155": "We have sent proper proper medicine to Cx",
    "252160": "We have sent proper medicine to Cx",
    "252168": "We have sent proper medicine to Cx",
    "252170": "We have sent proper medicine to Cx",
    "252174": "We have sent proper medicine to Cx",
    "252083": "We have sent proper medicine to Cx",
    "252112": "We have sent proper medicine to Cx",
    "252229": None,
    "252177": None,
    "252187": "We have sent proper medicine to Cx",
    "252172": "We have sent wrong sku to Cx",
    "252199": "We have sent wrong sku to Cx",
    "252139": None,
    "252154": "That batch is not in our inventory / We have sent proper medicine to Cx",
    "252034": None,
    "252207": None,
}

TICKETS = [
    {"ticket_id": "252224", "order_id": 3383809, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T13:30:20"},
    {"ticket_id": "252157", "order_id": 3351910, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T10:27:38"},
    {"ticket_id": "252041", "order_id": 3280391, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T04:48:56"},
    {"ticket_id": "252219", "order_id": 3349841, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T13:25:26"},
    {"ticket_id": "252196", "order_id": 3338561, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T12:23:42"},
    {"ticket_id": "252210", "order_id": 3331716, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T12:57:57"},
    {"ticket_id": "252167", "order_id": 3352948, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T10:55:34"},
    {"ticket_id": "252193", "order_id": 3341342, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T12:13:38"},
    {"ticket_id": "252212", "order_id": 3312631, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T13:02:33"},
    {"ticket_id": "252213", "order_id": 3311178, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T13:04:53"},
    {"ticket_id": "252130", "order_id": 3351721, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T07:48:51"},
    {"ticket_id": "252155", "order_id": 3183944, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T10:22:19"},
    {"ticket_id": "252160", "order_id": 3370292, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T10:36:38"},
    {"ticket_id": "252168", "order_id": 3385467, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T11:00:26"},
    {"ticket_id": "252170", "order_id": 3342441, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T11:03:46"},
    {"ticket_id": "252174", "order_id": 3319912, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T11:20:30"},
    {"ticket_id": "252083", "order_id": 3225380, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T06:06:32"},
    {"ticket_id": "252112", "order_id": 3342175, "category": "Missing/Wrong Qty", "created_time": "2026-08-11T07:13:39"},
    {"ticket_id": "252229", "order_id": 3377556, "category": "Wrong Medicines", "created_time": "2026-08-11T13:54:57"},
    {"ticket_id": "252177", "order_id": None, "category": "Wrong Medicines", "created_time": "2026-08-11T11:26:20"},
    {"ticket_id": "252187", "order_id": 3331405, "category": "Wrong Medicines", "created_time": "2026-08-11T11:48:33"},
    {"ticket_id": "252172", "order_id": 3309457, "category": "Wrong Medicines", "created_time": "2026-08-11T11:07:13"},
    {"ticket_id": "252199", "order_id": 3236098, "category": "Wrong Medicines", "created_time": "2026-08-11T12:30:09"},
    {"ticket_id": "252139", "order_id": 3304901, "category": "Wrong Medicines", "created_time": "2026-08-11T08:43:07"},
    {"ticket_id": "252154", "order_id": 3322180, "category": "Expiry Issue", "created_time": "2026-08-11T10:18:31"},
    {"ticket_id": "252034", "order_id": 3287652, "category": "Damaged/Defective", "created_time": "2026-08-11T03:58:24"},
    {"ticket_id": "252207", "order_id": 3343936, "category": "Damaged/Defective", "created_time": "2026-08-11T12:41:57"},
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
#
# 2026-08-13 run note: added "qty short" alongside "short qty" - ticket 252210's
# WH comment read "we have sent cerecetam syrup 1 qty short to Cx", a genuine
# admission whose word order ("qty short" not "short qty") the original phrase
# list didn't cover. Confirmed by reading the full sentence for intent, not
# just the substring match.
ADMISSION_PHRASES = ["wrong sku", "wrong item", "wrong qty", "wrong medicine",
                      "short qty", "qty short", "less qty", "sent short", "sent wrong", "missing qty"]

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
    "252219": {"picker": "Aniket_LKO", "packer": "Shivam.J_LKO", "qc": "Raj.V_LKO", "manifester": "Vinod_LKO"},
    "252210": {"picker": "Shashikumar_BLRWH", "packer": "Mukund_BLRWH", "qc": "kannanmuthu_BLRWH", "manifester": "Mustaqeem_BLRWH"},
    "252172": {"picker": "VitthalG_MUM", "packer": "MaheshK_MUM", "qc": "AnshuG_MUM", "manifester": "Hussain_MUM"},
    "252199": {"picker": "Veena_BLRWH / Supritha", "packer": "Veena_BLRWH", "qc": "Shwetha_BLRWH", "manifester": "Nagesh"},
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
    "generated_at": "2026-08-13T13:44:22Z",
    "for_date": "2026-08-11",
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
