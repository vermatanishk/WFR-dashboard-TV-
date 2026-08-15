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

2026-08-14 run note (for_date 2026-08-12): 41 T-2 tickets pulled, 3 genuine WH
admissions (all "we have sent wrong sku to Cx", all in Wrong Medicines) -
252448, 252452, 252284. Full comment threads read for every ticket before
classifying (per the 251580 lesson). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD issued" note - the two
admitted tickets with a later L2 action (252452 "Return Pickup Initiated",
252284 "claim accepted / Refund Processed") are consistent with acceptance,
not a discrepancy. Location join spot-checked for all 3 WH-Accepted orders:
3297683/3378028 -> Bangalore (usernames _BLRWH), 3386346 -> Mumbai (usernames
_MUM) - all matched. 0/39 non-null order_ids resolved to Unknown location.

2026-08-15 run note (for_date 2026-08-13): 31 T-2 tickets pulled (18
Missing/Wrong Qty, 9 Wrong Medicines, 1 Expiry Issue, 3 Damaged/Defective).
6 genuine WH admissions: 252650, 252655, 252582 ("we have sent short qty to
Cx", all Missing/Wrong Qty) and 252665, 252545, 252531 ("we have sent wrong
sku to Cx", all Wrong Medicines). Full comment threads read for every ticket
before classifying. Two tickets (252639, 252636) both referencing order
3395307 had a Warehouse-role comment that was neither an admission nor a
denial ("3395307 from this order id/ticket raised 3 times a day, same
issue" - a note about duplicate tickets) - correctly classified False by the
"otherwise -> False" branch, not miscounted as an admission via the "raised"
substring. No instance this run of a genuine WH admission followed by a
contradicting L2 "BOD issued" note - all 6 admitted tickets' later L2 notes
("Return Pickup Initiated" x3, "claim accepted / refund will be process
shortly" x2, and one still-pending duplicate-linked ticket) are consistent
with acceptance, not a discrepancy. No ClickHouse "Low-Value COG" remarks
encountered (not queried this run - text-only classification). Location
join spot-checked for all 6 WH-Accepted orders (exceeding the usual 2-3):
3395307 -> Delhi (Pooja_B_DEL/Ashma_DEL/Neeru_DEL/Kishan_DEL), 3410778 ->
Mumbai (JyotiD_MUM/JyotiG_MUM/JayeshW_MUM/Gauravj_MUM), 3396829 -> Mumbai
(AmishaG_MUM/PranjalG_MUM/KasturiR_MUM/Gauravj_MUM), 3363110 -> Mumbai
(ShivamS_MUM/TarunP_MUM/AnshuG_MUM/Gauravj_MUM), 3345916 -> Delhi
(MD_Neshar_DEL/Kuldeep_Del/Shailesh_DEL/Ronu_DEL), 3373049 -> Bangalore
(Aravind_BLRWH/Mukund_BLRWH/kannanmuthu_BLRWH/Mustaqeem_BLRWH) - all 6
matched, join confirmed correct. 0/28 unique non-null order_ids resolved to
Unknown location. Two tickets had no linkable Order ID (252514 "N/A",
252517 "N/A") and are excluded from the location join but still count in
the tickets total; neither had a Warehouse-role admission.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join (on order_id,
# NOT the internal "id" column - see docstring above).
ORDER_LOCATION = {
    3017846: "Delhi", 3258516: "Mumbai", 3348246: "Delhi", 3349022: "Delhi",
    3354677: "Bangalore", 3363172: "Bangalore", 3366721: "Mumbai", 3395307: "Delhi",
    3407150: "Delhi", 3410778: "Mumbai", 3324395: "Delhi", 3361684: "Bangalore",
    3362740: "Delhi", 3363110: "Mumbai", 3364636: "Delhi", 3368623: "Delhi",
    3371334: "Mumbai", 3373049: "Bangalore", 3374540: "Delhi", 3377273: "Delhi",
    3390585: "Delhi", 3392341: "Kolkata", 3393111: "Delhi", 3396829: "Mumbai",
    3398608: "Bangalore", 3280494: "Delhi", 3345916: "Delhi", 3373205: "Kolkata",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any) -
# confirmed by reading the FULL comment list for every ticket, not just the latest.
WH_COMMENT = {
    "252661": "We have sent proper medicine to Cx",
    "252639": "3395307 from this order id ticket raised 3 times a day, same issue",
    "252650": "We have sent short qty to Cx",
    "252655": "We have sent short qty to Cx",
    "252651": "We have sent proper medicine to Cx",
    "252656": "We have sent proper medicine to Cx",
    "252563": "We have sent proper medicine to Cx",
    "252597": "We have sent proper medicine to Cx",
    "252636": "3395307 from this order ticket raised 3 times a day, same issue",
    "252582": "We have sent short qty to Cx",
    "252586": "We have sent proper medicine to Cx",
    "252589": "We have sent proper medicine to Cx",
    "252590": "We have sent proper medicine to Cx",
    "252662": "We have sent proper medicine to Cx",
    "252666": "We have sent proper medicine to Cx",
    "252596": "We have sent proper medicine to Cx",
    "252649": "We have sent proper medicine to Cx",
    "252587": "We have sent proper medicine to Cx",
    "252673": "We have sent proper medicine to Cx",
    "252669": "Footage not found because it is under maintenance",
    "252665": "We have sent wrong sku to Cx",
    "252539": "We have sent proper medicine to Cx",
    "252545": "We have sent wrong sku to Cx",
    "252608": "We have sent proper medicine to Cx",
    "252531": "We have sent wrong sku to Cx",
    "252533": "We have sent proper medicine to Cx",
    "252514": None,
    "252642": None,
    "252635": None,
    "252553": "We have sent proper medicine to Cx",
    "252517": None,
}

TICKETS = [
    {"ticket_id": "252661", "order_id": 3354677, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T17:33:59"},
    {"ticket_id": "252639", "order_id": 3395307, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T16:17:13"},
    {"ticket_id": "252650", "order_id": 3395307, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T16:55:30"},
    {"ticket_id": "252655", "order_id": 3410778, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T17:07:47"},
    {"ticket_id": "252651", "order_id": 3390585, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T16:57:06"},
    {"ticket_id": "252656", "order_id": 3258516, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T17:09:53"},
    {"ticket_id": "252563", "order_id": 3366721, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T12:08:46"},
    {"ticket_id": "252597", "order_id": 3361684, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:49:10"},
    {"ticket_id": "252636", "order_id": 3395307, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T16:10:09"},
    {"ticket_id": "252582", "order_id": 3396829, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:18:30"},
    {"ticket_id": "252586", "order_id": 3393111, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:24:01"},
    {"ticket_id": "252589", "order_id": 3362740, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:28:47"},
    {"ticket_id": "252590", "order_id": 3398608, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:32:03"},
    {"ticket_id": "252662", "order_id": 3377273, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T17:37:34"},
    {"ticket_id": "252666", "order_id": 3368623, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T17:46:59"},
    {"ticket_id": "252596", "order_id": 3324395, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:46:25"},
    {"ticket_id": "252649", "order_id": 3364636, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T16:54:19"},
    {"ticket_id": "252587", "order_id": 3371334, "category": "Missing/Wrong Qty", "created_time": "2026-08-13T13:25:43"},
    {"ticket_id": "252673", "order_id": 3407150, "category": "Wrong Medicines", "created_time": "2026-08-13T18:12:18"},
    {"ticket_id": "252669", "order_id": 3373205, "category": "Wrong Medicines", "created_time": "2026-08-13T17:53:07"},
    {"ticket_id": "252665", "order_id": 3363110, "category": "Wrong Medicines", "created_time": "2026-08-13T17:44:02"},
    {"ticket_id": "252539", "order_id": 3349022, "category": "Wrong Medicines", "created_time": "2026-08-13T10:59:11"},
    {"ticket_id": "252545", "order_id": 3345916, "category": "Wrong Medicines", "created_time": "2026-08-13T11:09:00"},
    {"ticket_id": "252608", "order_id": 3363172, "category": "Wrong Medicines", "created_time": "2026-08-13T14:17:48"},
    {"ticket_id": "252531", "order_id": 3373049, "category": "Wrong Medicines", "created_time": "2026-08-13T10:35:38"},
    {"ticket_id": "252533", "order_id": 3348246, "category": "Wrong Medicines", "created_time": "2026-08-13T10:40:42"},
    {"ticket_id": "252514", "order_id": 3280494, "category": "Wrong Medicines", "created_time": "2026-08-13T09:08:37"},
    {"ticket_id": "252642", "order_id": 3017846, "category": "Expiry Issue", "created_time": "2026-08-13T16:30:02"},
    {"ticket_id": "252635", "order_id": 3374540, "category": "Damaged/Defective", "created_time": "2026-08-13T16:09:05"},
    {"ticket_id": "252553", "order_id": 3392341, "category": "Damaged/Defective", "created_time": "2026-08-13T11:27:24"},
    {"ticket_id": "252517", "order_id": None, "category": "Damaged/Defective", "created_time": "2026-08-13T09:35:13"},
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
    "252650": {"picker": "Pooja_B_DEL", "packer": "Ashma_DEL", "qc": "Neeru_DEL", "manifester": "Kishan_DEL"},
    "252655": {"picker": "JyotiD_MUM", "packer": "JyotiG_MUM", "qc": "JayeshW_MUM", "manifester": "Gauravj_MUM"},
    "252582": {"picker": "AmishaG_MUM", "packer": "PranjalG_MUM", "qc": "KasturiR_MUM", "manifester": "Gauravj_MUM"},
    "252665": {"picker": "ShivamS_MUM", "packer": "TarunP_MUM", "qc": "AnshuG_MUM", "manifester": "Gauravj_MUM"},
    "252545": {"picker": "MD_Neshar_DEL", "packer": "Kuldeep_Del", "qc": "Shailesh_DEL", "manifester": "Ronu_DEL"},
    "252531": {"picker": "Aravind_BLRWH", "packer": "Mukund_BLRWH", "qc": "kannanmuthu_BLRWH", "manifester": "Mustaqeem_BLRWH"},
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
    "generated_at": "2026-08-15T13:42:37Z",
    "for_date": "2026-08-13",
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
