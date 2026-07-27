"""
Builds the Zoho EOD tab dataset: yesterday's mis-shipment tickets only,
classified WH-Accepted purely by category (text-based, no ClickHouse
return-record dependency) per the accountability-tracker requirement -
"even if the return isn't processed yet, we still see it at EOD".

WH-Accepted (text) = category is Missing/Wrong Qty ("short qty") or
Wrong Medicines ("incorrect item sent"). Damaged/Defective and Expiry
are tracked but not counted WH-Accepted under this definition, since
they aren't necessarily a picking error.

Location comes from marketplace_orders.warehouse_id directly (not the
return_request join used elsewhere), since same-day tickets usually
have no return record yet.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

TEXT_WH_ACCEPTED_CATEGORIES = {"Missing/Wrong Qty", "Wrong Medicines"}

# order_id -> (warehouse_name, city), from ClickHouse marketplace_orders join
ORDER_LOCATION = {
    3037230: "Kolkata", 3120313: "Kolkata", 3120838: "Lucknow", 3147111: "Delhi",
    3142506: "Kolkata", 3164368: "Delhi", 3107816: "Delhi", 3171395: "Kolkata",
    3164189: "Bangalore", 3111787: "Bangalore", 3159511: "Bangalore",
    3145977: "Mumbai", 3136382: "Lucknow", 3106929: "Bangalore", 3156143: "Kolkata",
    3123162: "Bangalore", 2848423: "Mumbai", 3169351: "Delhi", 3151215: "Delhi",
    3132055: "Delhi", 3122871: "Delhi", 3151349: "Kolkata", 3141425: "Kolkata",
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

out_tickets = []
for t in TICKETS:
    wh_accepted = t["category"] in TEXT_WH_ACCEPTED_CATEGORIES
    out_tickets.append({
        **t,
        "location": ORDER_LOCATION.get(t["order_id"], "Unknown"),
        "wh_accepted_text": wh_accepted,
        "reason": (
            f"Category '{t['category']}' is a WH-fulfillment issue (short qty / wrong item) - "
            "counted WH-Accepted immediately for EOD accountability, independent of return status."
            if wh_accepted else
            f"Category '{t['category']}' is not counted WH-Accepted under the text-based EOD rule "
            "(only Missing/Wrong Qty and Wrong Medicines are)."
        ),
    })

eod_data = {
    "generated_at": "2026-07-27T13:30:00Z",
    "for_date": "2026-07-26",
    "methodology": "WH-Accepted here is TEXT-BASED: any ticket in Missing/Wrong Qty ('short qty') or Wrong Medicines ('incorrect item sent') is counted immediately, without waiting for a ClickHouse return record - so ops has same-day accountability. Location comes from marketplace_orders.warehouse_id directly (not the return-request join), since same-day tickets usually have no return record yet.",
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
