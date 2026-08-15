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
    "252288": "We have sent proper medicine to Cx",
    "252468": "We have sent proper medicine to Cx",
    "252463": "We have sent proper medicine to Cx",
    "252451": "We have sent proper medicine to Cx",
    "252440": "We have sent proper medicine to Cx",
    "252438": "We have sent proper medicine to Cx",
    "252363": "We have sent proper medicine to Cx",
    "252410": "We have sent proper medicine to Cx",
    "252406": "We have sent proper medicine to Cx",
    "252453": "We have sent proper medicine to Cx",
    "252397": "Footage not found because it is under maintenance",
    "252359": "We have sent proper medicine to Cx",
    "252402": "We have sent proper medicine to Cx",
    "252469": "We have sent proper medicine to Cx",
    "252423": "We have sent proper medicine to Cx",
    "252418": "We have sent proper medicine to Cx",
    "252445": "We have sent proper medicine to Cx",
    "252435": "We have sent proper medicine to Cx",
    "252302": "We have sent proper medicine to Cx",
    "252361": "We have sent proper medicine to Cx",
    "252354": "We have sent proper medicine to Cx",
    "252350": None,
    "252308": "We have sent proper medicine to Cx",
    "252383": "We have sent proper medicine to Cx",
    "252448": "We have sent wrong sku to Cx",
    "252457": "We have sent proper medicine to Cx",
    "252390": None,
    "252373": "We have sent proper medicine to Cx",
    "252413": "We have sent proper medicine to Cx",
    "252486": None,
    "252452": "We have sent wrong sku to Cx",
    "252304": "Kindly share images of all medicine what are wrong medicine you have received",
    "252284": "We have sent wrong sku to Cx",
    "252331": "We have sent proper medicine to Cx",
    "252344": None,
    "252297": "We have sent proper medicine to Cx",
    "252252": None,
    "252301": None,
    "252487": None,
    "252353": None,
    "252479": "Kindly share the order id",
}

TICKETS = [
    {"ticket_id": "252288", "order_id": 3243551, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T04:47:49"},
    {"ticket_id": "252468", "order_id": 3289051, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T13:23:58"},
    {"ticket_id": "252463", "order_id": 3358499, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T13:00:49"},
    {"ticket_id": "252451", "order_id": 3286570, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T12:26:51"},
    {"ticket_id": "252440", "order_id": 3367493, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T11:58:58"},
    {"ticket_id": "252438", "order_id": 3301505, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T11:55:38"},
    {"ticket_id": "252363", "order_id": 3387986, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T07:58:07"},
    {"ticket_id": "252410", "order_id": 3381612, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T10:33:35"},
    {"ticket_id": "252406", "order_id": 3369638, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T10:24:28"},
    {"ticket_id": "252453", "order_id": 3395992, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T12:39:19"},
    {"ticket_id": "252397", "order_id": 3352386, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T10:09:02"},
    {"ticket_id": "252359", "order_id": 3384884, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T07:50:00"},
    {"ticket_id": "252402", "order_id": 3377878, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T10:20:22"},
    {"ticket_id": "252469", "order_id": 3387427, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T13:26:10"},
    {"ticket_id": "252423", "order_id": 3372609, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T11:20:33"},
    {"ticket_id": "252418", "order_id": 3381072, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T11:05:59"},
    {"ticket_id": "252445", "order_id": 3342944, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T12:10:13"},
    {"ticket_id": "252435", "order_id": 3348149, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T11:51:08"},
    {"ticket_id": "252302", "order_id": 3361684, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T05:36:08"},
    {"ticket_id": "252361", "order_id": 3376411, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T07:56:19"},
    {"ticket_id": "252354", "order_id": 3383888, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T07:34:08"},
    {"ticket_id": "252350", "order_id": 3153746, "category": "Missing/Wrong Qty", "created_time": "2026-08-12T07:23:52"},
    {"ticket_id": "252308", "order_id": 3352871, "category": "Wrong Medicines", "created_time": "2026-08-12T06:03:25"},
    {"ticket_id": "252383", "order_id": 3369488, "category": "Wrong Medicines", "created_time": "2026-08-12T08:59:53"},
    {"ticket_id": "252448", "order_id": 3378028, "category": "Wrong Medicines", "created_time": "2026-08-12T12:19:55"},
    {"ticket_id": "252457", "order_id": 3365834, "category": "Wrong Medicines", "created_time": "2026-08-12T12:46:35"},
    {"ticket_id": "252390", "order_id": 3347737, "category": "Wrong Medicines", "created_time": "2026-08-12T09:55:47"},
    {"ticket_id": "252373", "order_id": 3385908, "category": "Wrong Medicines", "created_time": "2026-08-12T08:23:56"},
    {"ticket_id": "252413", "order_id": 3383949, "category": "Wrong Medicines", "created_time": "2026-08-12T10:42:05"},
    {"ticket_id": "252486", "order_id": 3346126, "category": "Wrong Medicines", "created_time": "2026-08-12T16:19:41"},
    {"ticket_id": "252452", "order_id": 3386346, "category": "Wrong Medicines", "created_time": "2026-08-12T12:29:53"},
    {"ticket_id": "252304", "order_id": 3290510, "category": "Wrong Medicines", "created_time": "2026-08-12T05:38:57"},
    {"ticket_id": "252284", "order_id": 3297683, "category": "Wrong Medicines", "created_time": "2026-08-12T04:30:58"},
    {"ticket_id": "252331", "order_id": 3295711, "category": "Wrong Medicines", "created_time": "2026-08-12T06:27:57"},
    {"ticket_id": "252344", "order_id": 3382423, "category": "Wrong Medicines", "created_time": "2026-08-12T07:06:19"},
    {"ticket_id": "252297", "order_id": 3372512, "category": "Wrong Medicines", "created_time": "2026-08-12T05:19:34"},
    {"ticket_id": "252252", "order_id": None, "category": "Wrong Medicines", "created_time": "2026-08-11T18:30:31"},
    {"ticket_id": "252301", "order_id": 3378807, "category": "Wrong Medicines", "created_time": "2026-08-12T05:29:15"},
    {"ticket_id": "252487", "order_id": 2966043, "category": "Damaged/Defective", "created_time": "2026-08-12T16:40:49"},
    {"ticket_id": "252353", "order_id": 3368100, "category": "Damaged/Defective", "created_time": "2026-08-12T07:33:45"},
    {"ticket_id": "252479", "order_id": None, "category": "Damaged/Defective", "created_time": "2026-08-12T14:36:45"},
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
    "252448": {"picker": "Prabhu_BLRWH / Salmabanu_BLRWH", "packer": "Suchithra", "qc": "Fardeen_BLRWH", "manifester": "Vasantha"},
    "252452": {"picker": "AniketP_MUM", "packer": "JyotiG_MUM", "qc": "KritikaD_MUM", "manifester": "Hussain_MUM"},
    "252284": {"picker": "Shashikumar_BLRWH", "packer": "Mukund_BLRWH", "qc": "Raksha_BLRWH", "manifester": "Vasantha"},
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
    "generated_at": "2026-08-14T13:49:34Z",
    "for_date": "2026-08-12",
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
