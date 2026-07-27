from __future__ import annotations

# Canonical mapping: raw Zoho `Sub-disposition` -> one of the 5 mis-shipment categories.
# Extend this dict as new free-text variants show up in the live sheet.

CATEGORY_MAP = {
    # Missing / Wrong Qty
    "missing or less quantity received": "Missing/Wrong Qty",
    "incomplete order": "Missing/Wrong Qty",
    "iincomplete order": "Missing/Wrong Qty",
    "incomplete order delivered": "Missing/Wrong Qty",
    "short quantity": "Missing/Wrong Qty",
    "less quantity received": "Missing/Wrong Qty",

    # Wrong Medicines
    "wrong item delivered": "Wrong Medicines",
    "wrong medicine": "Wrong Medicines",
    "received wrong medicines": "Wrong Medicines",

    # Expiry Issue
    "expired or near expiry": "Expiry Issue",
    "expiry issue": "Expiry Issue",
    "near expiry medicines received": "Expiry Issue",

    # Damaged / Defective Items
    "spilled or broken or spoiled contents": "Damaged/Defective",
    "damaged or defective packaging": "Damaged/Defective",
    "order/item damage": "Damaged/Defective",
    "defective device or accessory": "Damaged/Defective",

    # Switch Orders
    "order switch": "Switch Orders",
    "order swap": "Switch Orders",
    "cross customer swap": "Switch Orders",
}


def normalize(sub_disposition: str) -> str | None:
    """Map a raw Zoho Sub-disposition string to one of the 5 canonical categories.

    Returns None if the ticket is not a mis-shipment ticket at all.
    """
    if not sub_disposition:
        return None
    key = sub_disposition.strip().lower()
    return CATEGORY_MAP.get(key)


# ClickHouse "Accepted" logic (Section 2.2 of the requirements doc).
# An order is Accepted if it has a marketplace_return_request row where:
#   - the item-level `reason` matches the category's reason pattern, AND
#   - the request-level `remark` matches a WH-fault-CONFIRMED pattern
#     (explicitly excluding policy/BOD/CX-side remarks).
# This is our own reconstruction (validated against live samples on 2026-07-27) —
# review with ops before treating as final ground truth.

CATEGORY_REASON_PATTERNS = {
    "Missing/Wrong Qty": ["%incomplete order%", "%missing%", "%short%", "%less quantity%"],
    "Wrong Medicines": ["%wrong medic%", "%received wrong medic%", "%wrong item%"],
    "Expiry Issue": ["%expir%"],
    "Damaged/Defective": ["%damage%", "%defective%", "%spill%", "%spoil%", "%broken%"],
    "Switch Orders": ["%switch%", "%swap%"],
}

WH_FAULT_CONFIRMED_REMARK_PATTERNS = [
    "%incomplete order delivered%",
    "%wrong medicine delivered%",
    "%damaged medicine%",
    "%mrp mismatch%",
    "%wh confirmed%",
]

# Remarks that look plausible but do NOT confirm WH fault - excluded on purpose.
NON_WH_FAULT_REMARK_PATTERNS = [
    "%bod issued%",
    "%low-value cog%",
    "%nsz%",
    "%customer unreachable%",
    "%customer received correct%",
    "%customer changed%",
    "%return in transit%",
    "%expiry >%month%",
    "%validated%",  # ambiguous - doesn't explicitly say WH-fault
    "%qc completed successfully%",  # generic return-QC pass, not a fault admission
]

# Tab 1 "resolution" bucketing (WH-Accepted vs BOD), operationally simpler than
# the category-level Accepted logic above: any order WITH a marketplace_return_request
# row is either WH-Accepted (remark matches WH_FAULT_CONFIRMED_REMARK_PATTERNS) or,
# for everything else with a return on file (ambiguous remark, null remark, or an
# explicit customer-favor remark like "BOD Issued"/"Low-Value COG"/"Return In Transit"),
# bucketed as BOD. This is a deliberate simplification so
# WH Accepted + BOD == Total refunds/returns issued, always, by construction.
# Orders with NO return_request row at all are tracked separately as "no_return_record"
# and excluded from the refund/return total (nothing was actually processed).
def classify_resolution(reason: str | None, remark: str | None, has_return_record: bool) -> str:
    if not has_return_record:
        return "no_return_record"
    remark_l = (remark or "").lower()
    for pat in WH_FAULT_CONFIRMED_REMARK_PATTERNS:
        needle = pat.strip("%")
        if needle in remark_l:
            return "wh_accepted"
    return "bod"
