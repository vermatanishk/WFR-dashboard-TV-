"""Run: python3 pipeline/test_rca_trend.py
For All and for each return state, every parent row of rca_trend.json must equal the sum of its children in EVERY
column (3mo / 1mo / 2wk / each day); and for every row the three return states must add up to All."""
import json
from pathlib import Path

T = json.loads((Path(__file__).parent / "rca_trend.json").read_text())
ND = ["nd_" + n for n in ["Footage not available", "Batch not from our inventory", "CX image not clear", "Dependency not marked",
      "DocPharma order", "COGS < 100", "Agent mistake (WH marked, no WH comment)", "Return not received at WH", "Other WH note"]]
BUCKETS = ["dmb_" + k for k in ["primary_pack_breached", "carton_damaged", "outer_shipper_damaged", "leak_spill", "product_quality",
           "label_closure_defect", "no_visible_damage", "image_not_relevant"]]
GROUPS = [
    ("raised = accepted + rejected + no decision + not yet read", "raised", ["accepted", "rejected", "no_decision", "not_yet_read"]),
    ("no decision reasons", "no_decision", ND),
    ("wrong medicine: read + not read + not available", "wm", ["wm_read", "wm_unread", "wm_na"]),
    ("different medicine split", "wm_diff", ["wm_diff_bin", "wm_diff_batch", "wm_diff_other"]),
    ("same medicine diff pack split", "wm_variant", ["wm_variant_bin", "wm_variant_batch", "wm_variant_other"]),
    ("sku unreadable split", "wm_undet", ["wm_undet_bin", "wm_undet_batch", "wm_undet_other"]),
    ("item missing split", "mq_item", ["mq_im_pack", "mq_im_count", "mq_im_unid", "mq_im_pend"]),
    ("pack qty confusion split", "mq_im_pack", ["mq_im_pack_cust", "mq_im_pack_wh"]),
    ("pack WH / system split", "mq_im_pack_wh", ["mq_im_pack_inw", "mq_im_pack_cat", "mq_im_pack_acc"]),
    ("counting error split", "mq_im_count", ["mq_im_count_conf", "mq_im_count_elim"]),
    ("wrong medicine read children", "wm_read", ["wm_same", "wm_variant", "wm_diff", "wm_undet"]),
    ("expiry allocation split", "ex", ["ex_alloc_out", "ex_alloc_near", "ex_alloc_ok", "ex_alloc_undet"]),
    ("expiry photo: read + not read + not available", "ex", ["ex_read", "ex_unread", "ex_na"]),
    ("expiry photo outcomes", "ex_read", ["ex_img_expired", "ex_img_near", "ex_img_ok", "ex_img_batchonly", "ex_img_unclear"]),
    ("expiry differs: expired + not expired + not legible", "ex_diff", ["ex_diff_exp", "ex_diff_notexp", "ex_diff_unk"]),
    ("damaged cold / non-cold", "dm", ["dm_cold", "dm_nc"]),
    ("non-cold: read + not read + not available", "dm_nc", ["dm_nc_read", "dm_nc_unread", "dm_nc_na"]),
    ("non-cold buckets", "dm_nc_read", BUCKETS),
    ("missing qty = SKU + item", "mq", ["mq_sku", "mq_item"]),
    ("categories add to raised", "raised", ["wm", "ex", "dm", "mq", "sw", "mrp"]),
]


def cols(rows, key):
    r = next(x for x in rows if x["key"] == key)
    return [r["3mo"]["n"], r["1mo"]["n"], r["2wk"]["n"]] + [r["daily"][d]["n"] for d in T["days"]]


ok = True
variants = {"All": T, **{k: v for k, v in T["by_return"].items()}}
for vname, v in variants.items():
    for name, parent, kids in GROUPS:
        P = cols(v["rows"], parent)
        C = [sum(x) for x in zip(*[cols(v["rows"], k) for k in kids])]
        bad = [(i, p, c) for i, (p, c) in enumerate(zip(P, C)) if p != c]
        if bad:
            ok = False
            print("FAIL", vname, name, bad[:3])
print(("OK  " if ok else "FAIL"), f"{len(GROUPS)} additive groups x {len(variants)} variants")
n_bad = 0
for r in T["rows"]:
    k = r["key"]
    tot = cols(T["rows"], k)
    parts = [sum(x) for x in zip(*[cols(T["by_return"][s]["rows"], k) for s in T["by_return"]])]
    if tot != parts:
        n_bad += 1
        print("FAIL return states != All for", k)
print(("OK  " if not n_bad else "FAIL"), f"return states add up to All for {len(T['rows'])} rows")
raise SystemExit(0 if (ok and not n_bad) else 1)
