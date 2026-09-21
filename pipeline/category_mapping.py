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
    "defective or damaged device or accessory": "Damaged/Defective",

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


# NOTE: resolution (WH-Accepted / BOD / Considered BOD) is decided entirely
# by the Warehouse-team's own Zoho comment - see classify() in
# build_full_dataset.py and pipeline/wh_comment_classifier.py. This file
# used to also carry a ClickHouse-remark-based resolution path
# (WH_FAULT_CONFIRMED_REMARK_PATTERNS / NON_WH_FAULT_REMARK_PATTERNS /
# classify_resolution()); it was removed on 2026-09-21 because the remark
# field tracks "was this refunded," not "whose fault was it," and repeatedly
# contradicted the Warehouse team's own statement on real tickets. Do not
# reintroduce a remark-based fallback into the resolution logic.

CATEGORY_REASON_PATTERNS = {
    "Missing/Wrong Qty": ["%incomplete order%", "%missing%", "%short%", "%less quantity%"],
    "Wrong Medicines": ["%wrong medic%", "%received wrong medic%", "%wrong item%"],
    "Expiry Issue": ["%expir%"],
    "Damaged/Defective": ["%damage%", "%defective%", "%spill%", "%spoil%", "%broken%"],
    "Switch Orders": ["%switch%", "%swap%"],
}
