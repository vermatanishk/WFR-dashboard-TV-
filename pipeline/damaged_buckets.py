"""
Classifier buckets for the Damaged -> Non-cold -> image-read step (owner-defined 2026-10-14).
Cold-chain tickets are NEVER image-read (temperature complaint). For a non-cold ticket the session reads
the complaint photos of the complained return line and assigns exactly ONE bucket (priority top to bottom
when a photo shows several things). Never name a person as the cause.
"""
BUCKETS = [
    # key, label, where in the chain
    ("primary_pack_breached", "Primary pack breached: blister punctured/burst, sachet torn, strip crushed", "Packing / handling"),
    ("carton_damaged", "Individual carton crushed, torn or water-soaked; product intact", "Packing / handling"),
    ("outer_shipper_damaged", "Courier / outer shipper crushed or torn; product inside intact", "Transit handling"),
    ("leak_spill", "Liquid / gel leaked or spilled", "Closure / seal + packing"),
    ("product_quality", "Product itself defective (split tablet, lumpy formula, dose delivery)", "Manufacturer / supplier"),
    ("label_closure_defect", "Vial label peeled off / flip-off cap loose", "Manufacturer pack"),
    ("no_visible_damage", "Photo shows the product intact - no visible damage", "Not supported by the photo"),
    ("image_not_relevant", "Image not relevant: only the app logo, or a photo of a different product", "No usable evidence"),
]
# raw read labels folded into a bucket
ALIASES = {"no_evidence": "image_not_relevant", "wrong_item_in_photo": "image_not_relevant"}


def bucket(raw):
    return ALIASES.get(raw, raw)
