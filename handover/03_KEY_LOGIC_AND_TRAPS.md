# Key logic and traps

## Resolution of a ticket with a return record
Decided **only** by the Warehouse team's Zoho comment, never the ClickHouse `remark` (it tracks "refunded", not "whose fault";
~80% of remark-based "accepted" were real WH denials).
- cached `admitted` -> `wh_accepted`; `denied` -> `bod`
- no entry / `no_wh_comment` / `unrecognized` -> `considered_bod` (unconfirmed; always its own line, never merged into `bod`)
- no ClickHouse return row -> `no_return_record` (checked first, so a fresh admission can show 0 until the return row lands)
- Invariant: `wh_accepted + bod + considered_bod == returns issued` (`reconciles` in `build_report.py`). If False, stop and investigate.
- Large `considered_bod` is expected until WH-comment backfill catches up.

## Cache rules (`wh_text_check.json`)
- Only `admitted` / `denied` are final. `no_wh_comment` / `unrecognized` are provisional - re-read until past T-2.
- Never cache a verdict for a ticket younger than T-2 (WH needs ~2 days to comment).
- Pair comments to tickets by `ticketNumber`, **never by position** (`searchTickets` does not preserve order).
- Zoho `ticketNumber` (our `ticket_id`) is not the internal `id` that `getTicketComments` needs.
- Sync EOD verdicts into the cache for every run.

## Data traps
- ClickHouse `marketplace_orders`: join on `order_id`, **not** `id`.
- CDC tables: dedupe with `LIMIT 1 BY id`, drop `_peerdb_is_deleted`; do not filter `is_active` (it is 0).
- Tab 1 buckets by UTC date; EOD by IST date. Macro table and EOD are T-2 capped, rest of Tab 1 is not.
- Tickets with multi-order/placeholder Order IDs are dropped from Tab 1 (82 of 2,460) but counted in EOD.
- Complaint = (order, type); use the **final** return reason per (order, drug_code), not first/any (overstated wrong-medicine ~3x).
- RCA counts are unique per order, first ticket wins.
- Personnel leaderboards are rate-based (errors / throughput), track unattributed % explicitly.
- RFD: do not compare the two legacy pipelines' numbers; use "RFD" terminology, not "FDR".
- Repo is **public**: no names, phones, WH comment text or secrets in committed JSON; only IDs.

## Owner rules to preserve
Image-derived verdicts capped at `likely`; unreadable = null, never inferred; judge only the ordered SKU in photos;
cold-chain damage is never image-read; "Order not placed by customer" is out of scope; the standalone "RCA view" tab is retired
(its tree lives in the WFR funnel tab). Don't change complaint-baseline definitions without the owner.

## Known gaps (as of 2026-11-04)
~45% of tickets "Not yet read" for WH verdict at last RCA check; `bod`/`considered_bod` backfill incomplete; no structured
received-SKU/batch field in Zoho; untracked WIP files in the working tree (`funnel_returns_oct*.json`, `damage_images_raw.json`,
`damage30_sku_distribution.csv`, `damage_bucket_samples/`) - decide whether to commit or discard.
