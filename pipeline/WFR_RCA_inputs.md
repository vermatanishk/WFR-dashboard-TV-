# WFR root-cause cuts - inputs and incremental pulls (owner 2026-11-27)

Module: `pipeline/wfr_rca.py` (docstring has the cut definitions). Applied to EVERY in-scope wrong-medicine / missing-qty / expiry complaint of the last 60 days
(union of return requests + Zoho tickets) by `build_complaints.py::add_wfr_cuts` -> columns `WFR cut 1`, `WFR cut 2`, `WFR cut detail`, `WFR cut basis`.
Older rows read "Older than the 60-day RCA window". A complaint whose inputs are not pulled yet reads "Inputs pending" (gate `WFR root-cause inputs complete`).
`zoho_raw90/wfr_inputs_done.json` lists the orders (per type) and wrong-medicine brands whose inputs were pulled - append to it after every pull. NEVER overwrite the wfr_*.json
caches; UNION new rows. All ClickHouse pulls: CDC dedupe `ORDER BY _peerdb_version DESC LIMIT 1 BY id`, `_peerdb_is_deleted=0`, add `repeat('x',N) AS pad`, `save_ch_result.py`.

| file | content | query shape |
|---|---|---|
| `wfr_wm_ordered.json` | wrong medicine: (order, ordered drug) -> warehouse, ordered name, salt, bin | `marketplace_orders` (wh) + `mdm_master_drug_data` + `mdm_drug_warehouse_locations` (argMax short_hand_location) |
| `wfr_wm_batches.json` | batches / expiries allocated to the ordered SKU | `groupUniqArray(batch_number)`, `groupUniqArray(toString(expiry_date))` from `marketplace_order_item_batches` WHERE (order_id, master_drug_code) IN (...) |
| `wfr_wm_candidates.json` | per RECEIVED brand (read off the photo): up to 6 catalog SKUs (`display_name LIKE '<brand>%'`) with salt and `locs` = ["wh:bin"] | `mdm_master_drug_data` joined to `mdm_drug_warehouse_locations` |
| photo reads | received SKU name / batch / expiry | `rca_return_images_raw.jsonl` (return-item image URLs, reason != RTO) -> `rca_images.py` -> read sheets -> `rca_reads_add.py` + `merge_reads.py` (10 `|` fields) |
| `wfr_mq_lines.json` | return items of the order: reason, ret_qty, order_qty, missing_qty, name, pack_qty | `marketplace_return_items` x `marketplace_return_request` x `mdm_master_drug_data` |
| `pack_mapping_subset.json` | code -> {name, xl pack qty, base qty, Single/Pack} from the pack mapping workbook (Sheet1, header row 7) | workbook |
| `wfr_grn_store.json` | {checked_codes, rows}: GRN rows of the complained SKU codes (code, grn_qty, open_po_qty, grn_date) | `mdm_grn_po_deltas` |
| `mq_pack_text_flags.json` | ticket ids whose text mentions strips / pack of / combo (ids + pattern kinds only) | `scan_pack_text.py` (Zoho REST, incremental) |
| `wfr_exp_batches.json` | expiry: allocated batch rows (batch, expiry, alloc_at, qty), delivered_at, `inv_expiries` = distinct expiries of that batch in `mdm_warehouse_batch_inventory` | `marketplace_order_item_batches` + inventory |

Rules: expiry shelf life = batch expiry (day-1 expiry = end of month) minus ALLOCATION time; <0 expired, <=183 days near expiry, else allocation correct.
Second cut for expiry = the batch carries more than one expiry year-month in the warehouse inventory ("inverting" error).
Wrong medicine cut 1: same active salt or same brand = Same family; else name look/sound alike (similarity >= 0.70 or same consonant skeleton) = LASA; else Completely different.
Cut 2: bin sharing (same bin or rack, verified catalog candidate) > batch overlap (printed batch = allocated batch of the ordered SKU) > other.
Missing qty cut 1: SKU missing (a line claims >= ordered qty) vs item missing (partial). Cut 2: pack quantity confusion (GRN qty = pack size x PO qty before the complaint, or
catalog / MDM pack definition conflict) > single-vs-pack (item missing on a multipack SKU) > counting issue. Pick scans are never evidence.
