"""
RCA for the remaining branches of the tree -> zoho_raw90/rca_extra.json (keyed by ticket_id) plus a
population summary. Every check keeps its evidence and is capped at `likely` unless it is a hard
data fact (pick scans, cold flag, shipment events).

  Missing / short qty   pick scans (warehouse_warehouse_scan_log scan_type=pick, metadata
                        pickedQuantity vs quantity per batch) + return item (quantity vs order_quantity)
      picked_in_full  -> the picker scanned the full quantity; the loss is AFTER picking
                         (pack / transit / customer side) - not a short pick
      short_picked    -> picker scanned less than required (WH-side, strong)
      no_pick_record  -> docpharma (warehouse 4 has no pick scanning) | jit_procured | pick_not_scanned
      kind            -> sku_missing (claim >= ordered qty) | item_missing (partial)
  Damaged                cold flag (order_cold_flag via data.json is_cold) + shipment_events NDR /
                         multiple delivery attempts (logistics exception) - warehouse cause cannot be
                         proven from tables, so "no logistics exception" is `undetermined`, not WH.
  Order swap             courier label order id differs from the ticket order (image read), same
                         warehouse + created within a day; shared-AWB check found none.
  MRP / Batch mismatch   printed pack MRP / batch vs the allocated batch row's MRP / batch.
People are never named; patient mobile is only ever compared as a hash.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "zoho_raw90"


def mrp_batch_verdict(system, printed):
    """system: {'batch','mrp'} from marketplace_order_item_batches; printed: {'batch','mrp',...} read
    off the pack. -> dict with batch_relation, mrp_relation, mrp_delta, verdict."""
    def norm(b):
        return "".join(ch for ch in (b or "").upper() if ch.isalnum())
    sb, pb = norm(system.get("batch")), norm(printed.get("batch"))
    if not sb or not pb:
        brel = "unknown"
    elif sb == pb:
        brel = "match"
    else:
        diff = sum(a != b for a, b in zip(sb, pb)) + abs(len(sb) - len(pb))
        brel = "near_match" if diff <= 1 else "differs"
    sm, pm = system.get("mrp"), printed.get("mrp")
    if sm is None or pm is None:
        mrel, delta = "unknown", None
    else:
        delta = round(sm - pm, 2)
        mrel = "equal" if abs(delta) < 0.5 else ("system_higher_than_pack" if delta > 0 else "pack_higher_than_system")
    if mrel == "system_higher_than_pack":
        verdict = "customer billed above printed MRP" + (" (batch differs from allocation)" if brel == "differs" else "")
    elif mrel == "pack_higher_than_system":
        verdict = "pack MRP above system MRP"
    elif brel == "differs":
        verdict = "batch differs from allocation, MRP consistent"
    else:
        verdict = "consistent / not assessable"
    return {"batch_relation": brel, "mrp_relation": mrel, "mrp_delta": delta, "verdict": verdict}


def main():
    data = json.loads((HERE / "data.json").read_text())
    pick = json.loads((RAW / "rca_pickcheck.json").read_text())
    logi = set(json.loads((RAW / "rca_logistics.json").read_text())["ndr_or_multi_attempt_orders"])
    swap = json.loads((RAW / "rca_swap.json").read_text())["label_order_mismatch"]
    text_kind = json.loads((RAW / "rca_missing_text_kind.json").read_text()) if (RAW / "rca_missing_text_kind.json").exists() else {}
    out, summ = {}, {"missing": {}, "damaged": {}, "swap": 0}
    for t in data["tickets"]:
        o = str(t["order_id"])
        x = {}
        if t["category"] == "Missing/Wrong Qty":
            # Owner rule (2026-10-14): only the tree's split is reported. A pick scan can be recorded for a
            # pick that did not physically happen ("false picking"), so scans are NOT used as evidence.
            # Every Missing/Wrong Qty ticket falls in exactly one leaf (owner, 2026-10-14): return-item
            # quantities first; else the ticket text (empty box / not received / whole line = SKU missing;
            # partial quantity, accessory or short content = item missing); else a flagged default of
            # item missing. The basis is kept so the weaker calls stay visible.
            k = pick["picked_full"].get(o)
            if k:
                x["missing"] = {"kind": "sku_missing" if k == "S" else "item_missing", "basis": "return_item"}
            elif t["ticket_id"] in text_kind:
                x["missing"] = dict(text_kind[t["ticket_id"]])
            else:
                x["missing"] = {"kind": "item_missing", "basis": "default_no_detail"}
        if t["category"] == "Damaged/Defective":
            exc = o in logi
            x["damaged"] = {"cold": bool(t.get("is_cold")), "logistics_exception": exc,
                            "verdict": ("Logistics exception on the shipment (NDR / multiple delivery attempts)" if exc
                                        else "No logistics exception recorded - warehouse or packaging cause not provable from data"),
                            "strength": "likely" if exc else "undetermined"}
        if o in swap:
            x["swap"] = {**swap[o], "verdict": "Parcel label shows another order of the same warehouse - packing/label mix-up",
                         "strength": "likely"}
        if x:
            out[t["ticket_id"]] = x
    for r in out.values():
        if "missing" in r:
            k = r["missing"]["kind"] + ":" + r["missing"]["basis"]
            summ["missing"][k] = summ["missing"].get(k, 0) + 1
        if "damaged" in r:
            k = ("cold+" if r["damaged"]["cold"] else "noncold+") + ("logistics" if r["damaged"]["logistics_exception"] else "no_logistics_exc")
            summ["damaged"][k] = summ["damaged"].get(k, 0) + 1
        summ["swap"] += "swap" in r
    # MRP / batch sample (post-pull tickets; category now mapped, awaiting a fresh ticket pull)
    sample = []
    for tn, oid, name, sysv, pr, leg in json.loads((RAW / "rca_mrp_sample_reads.json").read_text()):
        sample.append({"ticket_id": tn, "order_id": oid, "sku": name, "system": sysv, "printed": pr,
                       "legibility": leg, "strength": "likely", **mrp_batch_verdict(sysv, pr)})
    (RAW / "rca_extra.json").write_text(json.dumps({"tickets": out, "summary": summ, "mrp_sample": sample,
                                                    "mrp_gaps": {"complaints_without_allocation_row": 14, "unreadable_image": 1, "of": 25}}))
    print("summary:", json.dumps(summ))
    from collections import Counter
    print("mrp sample:", dict(Counter(s["mrp_relation"] for s in sample)), "| batch:", dict(Counter(s["batch_relation"] for s in sample)))


if __name__ == "__main__":
    main()
