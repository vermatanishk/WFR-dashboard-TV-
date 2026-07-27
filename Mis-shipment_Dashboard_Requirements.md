# Mis-shipment Ops Dashboard — Requirements Spec

**Purpose:** Daily-refreshing operational dashboard for the ops team, summarizing mis-shipment tickets (total vs. warehouse-accepted), broken down by location and by personnel (picker/QC). Delivered as a daily snapshot for team review.

**Status of numbers in reference docs:** All figures in the attached PDFs/screenshot (3,862 / 3,496 / 5,068 / 315 tickets etc.) are from a prior one-off analysis using static CSV/parquet snapshots. They are **structural references only** — they show the shape of the output, not the live logic. The dashboard must be built on live, queryable sources (Zoho sheet + ClickHouse), not re-imported CSVs.

---

## 1. Data Sources

| # | Source | What it provides | Refresh | Status |
|---|--------|-------------------|---------|--------|
| 1 | **Zoho ticket export** — Google Sheet (`gid=350728808`, updated daily by data team) | Raw ticket-level data: `Ticket Id`, `Order ID`, `Created Time`, `Dispositions`, `Sub-disposition`, `Status`, `Team`, `Ticket Owner`, `Channel/Source`, `Ticket Description` | Daily (external) | Confirmed — structure inspected |
| 2 | **ClickHouse: `prx_prod_db.marketplace_return_request`** | `order_id`, `warehouse_id`, `remark` (WH-confirmation text), `created_at`, `return_status` | Live query | Confirmed |
| 3 | **ClickHouse: `prx_prod_db.marketplace_return_items`** | `return_request_id`, `reason` (customer-stated), `drug_name`, `missing_quantity` | Live query | Confirmed |
| 4 | **Warehouse to Location mapping** | Maps `warehouse_id` to human-readable location (Bangalore, Delhi, Mumbai, Lucknow, Kolkata, DocPharma, Mother WH-Affolife, etc.) | Static/rarely changes | **Not yet located** - need to confirm table or hardcode a mapping |
| 5 | **Picker / QC attribution source** | Per-order: who picked it, who QC'd it | N/A | **Not yet located.** Old analysis pulled this from an "order status ledger" + "item/batch detail" sheet - likely a WMS/fulfillment table not yet found in ClickHouse. **This is the single biggest open dependency - Tab 3 cannot be built without it.** |
| 6 | Chat/call ticket logs (if in scope) | Doc 2 shows the fuller universe (5,068 tickets) includes chat + call channels, not just Zoho/email | Unknown | **Open question - see Section 6** |

---

## 2. Core Definitions & Logic (must be locked before build)

### 2.1 "Total" tickets
A mis-shipment ticket = any Zoho ticket where `Dispositions` / `Sub-disposition` maps to one of the 5 standard categories (below). Two counting units matter and should both be tracked:
- **Ticket count** (raw rows - one order can generate multiple tickets)
- **Distinct order count** (`Order ID` deduped) - this is what actually matters operationally, since an order is the unit of investigation

### 2.2 "Accepted" tickets/orders
An order is **Accepted** if it has a matching row in `marketplace_return_request` where:
- `reason` (item-level, customer-stated) matches the category's reason pattern, **AND**
- `remark` (request-level, WH-confirmation text) matches a WH-fault-confirmed pattern (not a policy-check remark like "expiry >8 months")

This is the exact join logic already validated earlier in this conversation (reason + remark LIKE patterns, joined `return_request` <-> `return_items` on `order_id`). **This ClickHouse-derived number should be the single source of truth for "Accepted"** - not a manually reconciled CSV, which is what caused the 306 vs. 344 vs. 316 discrepancy across the reference docs.

### 2.3 Category taxonomy (5 standard categories)
| Category | Zoho disposition/sub-disposition maps to | Notes |
|---|---|---|
| Missing/Wrong Qty | "Missing or less quantity received", short qty, incomplete order | Largest category historically (~50%+ of volume) |
| Wrong Medicines | "Wrong item Delivered" | Has 2 sub-types worth tracking separately: **fulfillment error** (WH picked wrong item - real WH issue) vs. **order-entry error** (wrong item was ordered, usually a sales-agent mistake - NOT a WH issue). Getting this split right matters for fair WH attribution. |
| Expiry Issue | "Expired or near expiry" | Needs the reason+remark refinement from earlier in this conversation - raw `%expir%` catches unrelated policy remarks |
| Damaged/Defective Items | Spilled/broken packaging, spoiled contents, defective device/accessory | **New category, not in the original 4-category benchmark** - confirm ops wants this included from day one |
| Switch Orders | Cross-customer order swap | Low volume, historically highest accept % (~25%) |

**Requirement:** Build one canonical mapping table from raw Zoho `Sub-disposition` free text (which is messy - mixed case, typos like "iincomplete order") to these 5 categories, so it doesn't need re-deriving every refresh.

### 2.4 Personnel attribution logic (Tab 3)
For each **Accepted** order:
1. Look up picker_id and QC/checker_id from the order fulfillment ledger (source TBD - see 1.5)
2. Tag the order with its confirmed issue type: Wrong SKU / Short Qty / Switch Order (mirrors the screenshot's structure)
3. Aggregate counts by picker and separately by QC checker

**Known coverage gap:** in the old analysis, 42 of 315 accepted tickets (~13%) had no ledger-derived picker/QC data. Expect a similar "unattributed" bucket in the live version - track this explicitly rather than silently dropping those orders.

---

## Tab 1 - Everything: Total vs. Accepted

**Purpose:** Single top-level source of truth. What ops sees first every morning.

**Metrics:**
- Total tickets & total distinct orders (all categories combined)
- Accepted tickets & accepted distinct orders
- Accept % (accepted / total)
- Same 4 metrics broken down **by category** (5 rows: Missing/Wrong Qty, Wrong Medicines, Expiry, Damaged/Defective, Switch Orders)
- Trend: daily and rolling (7D / MTD / custom range) total vs. accepted, as a time series
- Day-over-day delta (up/down) on total volume and accept %

**Sources:** Zoho sheet (total, category-tagged) joined to ClickHouse accepted-orders logic (Section 2.2), on `Order ID`.

**Filters:** Date range (default: last 7 days + MTD toggle), category.

---

## Tab 2 - Location Deep-Dive

**Purpose:** Mirrors the Macro Pivot structure in Doc 1 - where are mis-shipments concentrated, and where does WH actually own the issue.

**Metrics:**
- Total vs. Accepted vs. Accept % by **Location x Category**, for the selected date range
- Location leaderboard: total volume, accept %, ranked
- Trend per location over time (to catch a location suddenly spiking)
- Grand total row/column (cross-check against Tab 1 totals - should always reconcile exactly, since it's the same live source)

**Sources:** Same as Tab 1, plus the warehouse-to-location mapping (Section 1, item 4 - **needs sourcing**).

**Filters:** Date range, category, location.

**Open question:** Confirm whether "Location" = shipping warehouse (`warehouse_id` from `return_request`) or something else (e.g., customer's city). The reference doc's locations (Bangalore, Delhi, Mumbai, Lucknow, Kolkata, DocPharma, Mother Warehouse-Affolife) read like **fulfillment warehouse names**, which matches `warehouse_id`.

---

## Tab 3 - Personnel Deep-Dive

**Purpose:** Mirrors the screenshot's "Top pickers" / "Top pharmacist checkers" tables - root-cause accountability at the individual level, for **Accepted** orders only (i.e., WH already admitted fault).

**Metrics:**
- Top pickers: count of Wrong SKU / Short Qty / Switch Order attributed, + total, ranked descending
- Top QC checkers: same breakdown
- % of accepted orders with attribution vs. unattributed (data-completeness metric - must be shown, not hidden)
- Optionally: trend of a given picker/checker's error rate over time, if volume-per-picker (denominator) is available - otherwise this stays a raw count leaderboard, not a rate, which is a meaningfully weaker signal for fairly judging staff

**Sources:** Accepted-orders list (from Tab 1 logic) joined to the picker/QC ledger - **source not yet located; this is the blocking dependency for this tab.**

**Filters:** Date range, issue type, picker/checker search.

**Caveat to flag to ops before this ships:** raw counts favor high-volume pickers looking "worse." If picker-level order volume (denominator) is available anywhere, an error-rate version of this table would be materially more useful and fairer than a leaderboard of raw counts - worth deciding before this becomes something used in performance conversations.

---

## 3. Data Quality / Reconciliation Notes (resolve before build)

1. **Multiple historical "total ticket" universes exist and disagree** - 3,862 (raw Zoho pull) vs. 3,496 (category-tagged pivot subset) vs. 5,068/5,099 (all-channel deduped, incl. chat/call, plus a new Damaged/Defective category). The live dashboard must pick **one** canonical definition - recommend: all Zoho tickets (whatever channels are in the live sheet) mapped to the 5 categories, deduped by `Order ID` + category. If chat/call tickets live outside the Zoho sheet, that's a scope decision for you, not something to silently merge in.
2. **"Accepted" also varied across sources** (306 / 344 / 316 in the reference docs, all manually reconciled). The live dashboard should compute this fresh from ClickHouse every refresh using the validated reason+remark logic - no manual reconciliation step.
3. **Sub-disposition text is messy** (case, typos, free text) - needs a cleanup/mapping layer, not raw string matching, or category totals will silently undercount.
4. **Location mapping and Personnel/ledger source are both unconfirmed** - these block Tab 2 and Tab 3 respectively until located. Recommend scanning ClickHouse databases (and asking the data team directly) for a fulfillment/WMS table with `order_id`, `picker_id`, `qc_id`, `warehouse_id`/location fields.

---

## 4. Delivery / Cadence

- **Refresh:** Daily (matching the Zoho sheet's update cadence)
- **Output format:** Static daily snapshot shareable with ops (e.g., scheduled export to PDF/image, or a link to a live-but-simple view) - confirm preferred format (Looker Studio scheduled email, Apps Script-generated PDF, or a hosted HTML dashboard snapshot)
- **Audience:** Ops team, daily review - implies the dashboard should load fast and lead with Tab 1's headline numbers, not require digging

---

## 5. Open Decisions Needed From You Before Build Starts

1. Scope: Zoho-only tickets, or all-channel (chat + call) like Doc 2's 5,068 universe?
2. Include "Damaged/Defective Items" as a 5th category from day one?
3. Confirm warehouse-to-location mapping source
4. Locate the picker/QC ledger source (blocking Tab 3)
5. Preferred delivery mechanism for the daily snapshot
