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
    3107185: "Mumbai", 3142847: "Mumbai", 3136033: "Delhi", 3116640: "Bangalore",
    3128155: "Bangalore", 3143740: "Bangalore", 3153502: "Delhi", 3154920: "Delhi",
    3161465: "Kolkata", 3150330: "Kolkata", 3098845: "Delhi", 3038162: "Delhi",
    3130995: "Mumbai", 3098238: "Bangalore", 3152646: "Lucknow", 3164799: "Delhi",
    3141605: "Bangalore", 3158835: "Delhi", 3163391: "Delhi", 3088226: "Mumbai",
    3174461: "Mumbai", 3119511: "Delhi", 3082131: "Delhi", 3136867: "Lucknow",
    3171959: "Delhi", 3162719: "Mumbai", 3163432: "Bangalore", 3164893: "Kolkata",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None/"" means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any).
WH_COMMENT = {
    "246862": "We have sent proper medicine to Cx",
    "246849": "We have sent proper medicine to Cx",
    "246835": "We have sent proper medicine to Cx to",
    "246440": "We have sent proper medicine to Cx",
    "246428": "We have sent proper medicine to Cx",
    "246449": "We have sent proper medicine to Cx",
    "246858": "We have sent proper medicine to Cx",
    "246856": "We have sent proper medicine to Cx",
    "246485": "We have sent proper medicine to Cx",
    "246486": "We have sent proper medicine to Cx",
    "246515": "We have sent proper medicine to Cx",
    "246763": "We have sent proper medicine to Cx",
    "246506": "We have sent proper medicine to Cx to",
    "246386": "We have sent proper medicine to cx",
    "246477": "We have sent proper medicine to Cx",
    "246521": "We have sent proper medicine to Cx",
    "246816": "We have sent proper medicine to Cx",
    "246773": "We have sent proper medicine to Cx (New Pak its not a wrong medicine)",
    "246283": "We have sent proper medicine to cx",
    "246442": "We have sent proper medicine to Cx",
    "246398": None,
    "246513": "We have sent proper medicine to Cx",
    "246770": None,
    "246302": None,
    "246391": "We have sent proper medicine to cx",
    "246578": "We have sent proper medicine to Cx",
    "246341": None,
    "246511": "We have sent proper medicine to Cx",
}

TICKETS = [
    {"ticket_id": "246862", "order_id": 3107185, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T13:17:25"},
    {"ticket_id": "246849", "order_id": 3142847, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T12:58:24"},
    {"ticket_id": "246835", "order_id": 3136033, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T12:34:08"},
    {"ticket_id": "246440", "order_id": 3116640, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T06:27:18"},
    {"ticket_id": "246428", "order_id": 3128155, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T06:18:09"},
    {"ticket_id": "246449", "order_id": 3143740, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T06:40:31"},
    {"ticket_id": "246858", "order_id": 3153502, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T13:12:10"},
    {"ticket_id": "246856", "order_id": 3154920, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T13:09:46"},
    {"ticket_id": "246485", "order_id": 3161465, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T07:29:54"},
    {"ticket_id": "246486", "order_id": 3150330, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T07:32:24"},
    {"ticket_id": "246515", "order_id": 3098845, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T08:04:06"},
    {"ticket_id": "246763", "order_id": 3038162, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T10:33:23"},
    {"ticket_id": "246506", "order_id": 3130995, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T07:53:58"},
    {"ticket_id": "246386", "order_id": 3098238, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T05:18:29"},
    {"ticket_id": "246477", "order_id": 3152646, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T07:23:45"},
    {"ticket_id": "246521", "order_id": 3164799, "category": "Missing/Wrong Qty", "created_time": "2026-07-27T08:10:58"},
    {"ticket_id": "246816", "order_id": 3141605, "category": "Wrong Medicines", "created_time": "2026-07-27T11:57:27"},
    {"ticket_id": "246773", "order_id": 3158835, "category": "Wrong Medicines", "created_time": "2026-07-27T10:52:23"},
    {"ticket_id": "246283", "order_id": 3163391, "category": "Wrong Medicines", "created_time": "2026-07-27T02:52:46"},
    {"ticket_id": "246442", "order_id": 3088226, "category": "Wrong Medicines", "created_time": "2026-07-27T06:29:38"},
    {"ticket_id": "246398", "order_id": 3174461, "category": "Wrong Medicines", "created_time": "2026-07-27T05:35:41"},
    {"ticket_id": "246513", "order_id": 3119511, "category": "Wrong Medicines", "created_time": "2026-07-27T07:59:10"},
    {"ticket_id": "246770", "order_id": 3082131, "category": "Wrong Medicines", "created_time": "2026-07-27T10:45:44"},
    {"ticket_id": "246302", "order_id": 3136867, "category": "Wrong Medicines", "created_time": "2026-07-27T03:23:14"},
    {"ticket_id": "246391", "order_id": 3171959, "category": "Damaged/Defective", "created_time": "2026-07-27T05:26:35"},
    {"ticket_id": "246578", "order_id": 3162719, "category": "Damaged/Defective", "created_time": "2026-07-27T08:50:53"},
    {"ticket_id": "246341", "order_id": 3163432, "category": "Damaged/Defective", "created_time": "2026-07-27T04:26:25"},
    {"ticket_id": "246511", "order_id": 3164893, "category": "Damaged/Defective", "created_time": "2026-07-27T07:56:25"},
]

# Genuine admission phrases the WH team uses when they DO own the mistake.
# "we have sent proper medicine" / "correct item" etc. are denials and never match.
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
    "247647": {"picker": "Kavana_BLRWH", "packer": "Kavana_BLRWH", "qc": "Shivaraj_BLRWH", "manifester": "Mustaqeem_BLRWH"},
    "247621": {"picker": "Gayatri.M_LKO / Anshu.S_LKO", "packer": "Anshu.S_LKO", "qc": "Arti_LKO", "manifester": "Vinod_LKO"},
    "247579": {"picker": "Sonu_DEL", "packer": "Sonu_DEL", "qc": "Shailesh_DEL", "manifester": "Ruksana_DEL"},
    "247651": {"picker": "Rahman_BLRWH", "packer": "Kavana_BLRWH", "qc": "kannanmuthu_BLRWH", "manifester": "Mustaqeem_BLRWH"},
    "247622": {"picker": "Ebinesar / Veena_BLRWH", "packer": "Veena_BLRWH", "qc": "Shwetha_BLRWH", "manifester": "Mustaqeem_BLRWH"},
}


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
    "generated_at": "2026-07-29T13:45:00Z",
    "for_date": "2026-07-27",
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
