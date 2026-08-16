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

2026-08-16 run note (for_date 2026-08-14): 23 T-2 tickets pulled (12
Missing/Wrong Qty, 9 Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective).
3 genuine WH admissions: 252817, 252847 ("we have sent short qty to Cx",
both Missing/Wrong Qty) and 252841 ("we have sent wrong sku to Cx", Wrong
Medicines). Full comment threads read for every ticket before classifying;
6 tickets (252857, 252894, 252835, 252867, 252759, 252754) had commentCount
0 in the search response - confirmed literally zero comments (no API call
needed to know there's no WH comment), correctly False via the "no WH
comment" branch. One WH comment this run, ticket 252771, read "Footage not
found because it is old order" - neither an admission nor a denial phrase
match, correctly classified False by the "otherwise -> False" branch (same
pattern as 252639/252636 on 2026-08-15). No instance this run of a genuine
WH admission followed by a contradicting L2 "BOD issued" note - all 3
admitted tickets' later L2 notes (252817 "claim accepted / Refund
Initiated", 252847 "Refund Initiated", 252841 "Return Pickup Initiated")
are consistent with acceptance, not a discrepancy. No ClickHouse "Low-Value
COG" remarks encountered (not queried this run - text-only classification).
Location join spot-checked for all 3 WH-Accepted orders: 3413731 -> Mumbai
(SapnaY_MUM/PayalA_MUM/NishaS_Mum/RohitK_MUM), 3374160 -> Bangalore
(Aravind_BLRWH/Mukund_BLRWH/Shabana_BLRWH/Mustaqeem_BLRWH), 3416857 ->
Mumbai (SwapnilP_MUM/AniketP_MUM/PrathmeshP_MUM/Hussain_MUM) - all 3
matched, join confirmed correct. 0/20 unique non-null order_ids resolved to
Unknown location. Two tickets had no linkable Order ID (252845 null,
252894 raw "N/A") and are excluded from the location join but still count
in the tickets total; neither had a Warehouse-role comment. Tickets 252768
and 252779 both reference order 3395075 (Wrong Medicines, duplicate-order
pattern like 2026-08-15's 252639/252636) - neither had a Warehouse-role
comment (both closed by L2 only), so no impact on WH-Accepted count.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join (on order_id,
# NOT the internal "id" column - see docstring above).
ORDER_LOCATION = {
    3047552: "Mumbai", 3239286: "Kolkata", 3018904: "Bangalore", 3239889: "Bangalore",
    3342412: "Bangalore", 3369996: "Lucknow", 3374005: "Mumbai", 3374160: "Bangalore",
    3380889: "Delhi", 3382101: "Mumbai", 3384973: "Bangalore", 3395075: "Delhi",
    3405082: "Bangalore", 3408292: "Mumbai", 3413534: "Kolkata", 3413731: "Mumbai",
    3414649: "Lucknow", 3416857: "Mumbai", 3418648: "Kolkata", 3431212: "Kolkata",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any) -
# confirmed by reading the FULL comment list for every ticket, not just the latest.
WH_COMMENT = {
    "252857": None,
    "252873": "We have sent proper medicine to Cx",
    "252817": "We have sent short qty to Cx",
    "252839": "We have sent proper medicine to Cx",
    "252842": "We have sent proper medicine to Cx",
    "252832": "We have sent proper medicine to Cx",
    "252871": "We have sent proper medicine to Cx",
    "252830": "We have sent proper medicine to Cx",
    "252845": None,
    "252894": None,
    "252847": "We have sent short qty to Cx",
    "252796": None,
    "252775": None,
    "252835": None,
    "252841": "We have sent wrong sku to Cx",
    "252771": "Footage not found because it is old order",
    "252867": None,
    "252759": None,
    "252779": None,
    "252768": None,
    "252748": None,
    "252710": None,
    "252754": None,
}

TICKETS = [
    {"ticket_id": "252857", "order_id": 3413534, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T12:33:40"},
    {"ticket_id": "252873", "order_id": 3374005, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T13:22:42"},
    {"ticket_id": "252817", "order_id": 3413731, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T10:08:20"},
    {"ticket_id": "252839", "order_id": 3239889, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T11:26:19"},
    {"ticket_id": "252842", "order_id": 3369996, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T11:33:04"},
    {"ticket_id": "252832", "order_id": 3405082, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T11:05:49"},
    {"ticket_id": "252871", "order_id": 3384973, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T13:16:29"},
    {"ticket_id": "252830", "order_id": 3239286, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T10:59:26"},
    {"ticket_id": "252845", "order_id": None, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T11:38:26"},
    {"ticket_id": "252894", "order_id": None, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T17:17:12"},
    {"ticket_id": "252847", "order_id": 3374160, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T11:43:48"},
    {"ticket_id": "252796", "order_id": 3047552, "category": "Missing/Wrong Qty", "created_time": "2026-08-14T08:41:08"},
    {"ticket_id": "252775", "order_id": 3342412, "category": "Wrong Medicines", "created_time": "2026-08-14T07:45:22"},
    {"ticket_id": "252835", "order_id": 3408292, "category": "Wrong Medicines", "created_time": "2026-08-14T11:10:33"},
    {"ticket_id": "252841", "order_id": 3416857, "category": "Wrong Medicines", "created_time": "2026-08-14T11:31:38"},
    {"ticket_id": "252771", "order_id": 3018904, "category": "Wrong Medicines", "created_time": "2026-08-14T07:41:06"},
    {"ticket_id": "252867", "order_id": 3380889, "category": "Wrong Medicines", "created_time": "2026-08-14T13:09:25"},
    {"ticket_id": "252759", "order_id": 3418648, "category": "Wrong Medicines", "created_time": "2026-08-14T07:16:15"},
    {"ticket_id": "252779", "order_id": 3395075, "category": "Wrong Medicines", "created_time": "2026-08-14T07:49:47"},
    {"ticket_id": "252768", "order_id": 3395075, "category": "Wrong Medicines", "created_time": "2026-08-14T07:38:54"},
    {"ticket_id": "252748", "order_id": 3382101, "category": "Wrong Medicines", "created_time": "2026-08-14T06:49:25"},
    {"ticket_id": "252710", "order_id": 3414649, "category": "Damaged/Defective", "created_time": "2026-08-14T02:27:32"},
    {"ticket_id": "252754", "order_id": 3431212, "category": "Damaged/Defective", "created_time": "2026-08-14T07:05:02"},
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
    "252817": {"picker": "SapnaY_MUM", "packer": "PayalA_MUM", "qc": "NishaS_Mum", "manifester": "RohitK_MUM"},
    "252847": {"picker": "Aravind_BLRWH", "packer": "Mukund_BLRWH", "qc": "Shabana_BLRWH", "manifester": "Mustaqeem_BLRWH"},
    "252841": {"picker": "AniketP_MUM", "packer": "AniketP_MUM", "qc": "PrathmeshP_MUM", "manifester": "Hussain_MUM"},
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
    "generated_at": "2026-08-16T13:41:06Z",
    "for_date": "2026-08-14",
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
