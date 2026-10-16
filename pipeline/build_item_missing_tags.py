"""
Item-missing x pack-mapping tags -> rca_item_missing_tags.csv / zoho_raw90/rca_item_missing_tags.json.
Inputs (saved from the pack mapping workbook + ClickHouse pulls, see RCA_Learnings_and_Decisions.md 12-14):
  rca_item_missing_orders.json  - order -> complained SKU code(s)
  rca_item_missing_sku.json     - SKU lines with mapping Single/Pack, base qty, mapping vs current MDM pack qty
  rca_item_missing_inward_sig.json - GRN rows whose qty = pack size x open PO qty (or reciprocal), since 1 Apr
Rules, first match wins: inward unit mismatch (signature GRN dated ON/BEFORE the order date - a later GRN cannot
explain an earlier shortage) > catalog / MDM pack definition > customer-end likely (pack SKU, WH did not accept)
> pack SKU WH accepted > counting error confirmed by WH > counting error by elimination.
Owner rule (2026-10-16): a partial short quantity is ITEM missing whether the SKU is sold as a single or a pack; SKU missing = zero units sent.
"""
import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"


def main():
    m = pd.read_json(RAW / "rca_item_missing_sku.json")
    sig = pd.read_json(RAW / "rca_item_missing_inward_sig.json")
    sig["grn_date"] = sig.grn_date.astype(str).str[:10]
    sku = pd.read_json(RAW / "rca_item_missing_orders.json")
    # reads rca.json (not the export) so the export can consume these tags without a circular dependency
    rca = json.loads((HERE / "rca.json").read_text())["rows"]
    INV = {"accepted": "Accepted", "rejected": "Rejected", "no_decision": "No decision", "not_yet_read": "Not yet read"}
    RET = {"accepted_refunded": "Raised - Accepted & refunded", "cancelled": "Raised - Cancelled", "rejected": "Raised - Rejected",
           "in_progress": "Raised - In progress", "not_raised": "Not raised"}
    ex = pd.DataFrame([{"order_id": r["order_id"], "Investigation bucket 1": INV.get(r["decision"], r["decision"]),
                        "Created date": r["date"], "Return request": RET.get(r["return_state"], r["return_state"])} for r in rca]
                      ).drop_duplicates("order_id").set_index("order_id")
    ratio = m[["xl_pack_qty", "cur_pack_qty"]].max(axis=1) / m[["xl_pack_qty", "cur_pack_qty"]].min(axis=1).replace(0, float("nan"))
    m["f_mdm2"] = m.f_mdm.fillna(False) & ((m.base_qty > 1) | (ratio >= 2))
    rows = []
    for o in sorted(sku.order_id.unique()):
        if o not in ex.index:
            continue
        r = ex.loc[o]
        inv, odate = r["Investigation bucket 1"], r["Created date"]
        gm = m[m.order_id == o]
        if gm.empty:
            rows.append(dict(order_id=o, structure="Not identified", flag_list="", bucket="Undetermined - SKU not identified",
                             wh=inv, ret=r["Return request"], skus=""))
            continue
        codes = set(gm.code.dropna().astype(int))
        inward = bool(len(sig[sig.code.isin(codes) & (sig.grn_date <= odate)]))
        fl = []
        structure = ("Pack (multipack per mapping)" if (gm.single_pack == "Pack").any()
                     else ("Not in mapping" if gm.single_pack.isna().all() else "Single"))
        if gm.f_conflict.notna().any(): fl.append("catalog conflict")
        if gm.f_mdm2.any(): fl.append("mapping changes MDM pack qty")
        if inward: fl.append("inward qty = pack-size x PO qty (before the order)")
        if gm.single_pack.isna().any(): fl.append("SKU missing from pack mapping")
        if inward: b = "Pack qty confusion - WH inward unit mismatch"
        elif set(fl) & {"catalog conflict", "mapping changes MDM pack qty", "SKU missing from pack mapping"}:
            b = "Pack qty confusion - catalog / MDM pack definition"
        elif structure.startswith("Pack") and inv != "Accepted":
            b = "Pack qty confusion - customer end likely (pack SKU, WH sent as invoiced)"
        elif structure.startswith("Pack"): b = "Pack qty confusion - pack SKU, WH accepted short"
        elif inv == "Accepted": b = "Counting error - confirmed by WH"
        else: b = "Counting error - by elimination (no pack flag, WH did not accept)"
        rows.append(dict(order_id=o, structure=structure, flag_list=" | ".join(fl), bucket=b, wh=inv, ret=r["Return request"],
                         skus="; ".join(gm.name.dropna().unique())[:110]))
    d = pd.DataFrame(rows)
    d.to_csv(HERE / "rca_item_missing_tags.csv", index=False)
    d[["order_id", "structure", "flag_list", "bucket"]].to_json(RAW / "rca_item_missing_tags.json", orient="records")
    print(d.bucket.value_counts().to_string())
    print(pd.crosstab(d.bucket, d.structure).to_string())


if __name__ == "__main__":
    main()
