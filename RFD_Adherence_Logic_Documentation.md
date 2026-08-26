# RFD Adherence Workbook — SQL Logic Documentation

Source: Metabase questions 36369, 36370, 39106, 39073 (ClickHouse, `prx_prod_db`), pulled into the "RFD ADHERENCE" Google Sheet via Apps Script (`ToolsetMetabasePrx`).

There are **two independent breach-detection pipelines** in this workbook, built at different times, using different definitions of "breach" and "procurement required." They are not directly comparable cell-for-cell even though the dashboard presents them side by side.

---

## Pipeline A — Cutoff/SLA engine (`OPS_BASE` + `Base_Data`)

**Q36369 → `OPS_BASE`** (17-day lookback, aggregated)
**Q36370 → `Base_Data`** (8-day lookback, order-level) — identical logic to 36369, just unaggregated

### 1. Order universe (`order_scope`)
- Orders created in the lookback window
- `status_id NOT IN (0,80,81,82,2,3,4,151,150)` — excludes cancelled/returned/draft-type statuses
- `warehouse_id IN (1,2,3,5,6)` — the 5 core warehouses (Bangalore, Delhi, Mumbai, Lucknow, Kolkata) — Patna/Hyderabad are **excluded** from this pipeline
- Test users excluded

### 2. Milestone timestamps (`status_rollup`)
Pulled from `marketplace_order_status_log`:
| Field | Definition |
|---|---|
| `odd_created_at` | First `status=1` event via `order_status_update` workflow |
| `so_date` | First `status=1` event via `zoho_status_update` workflow — i.e., when the order is confirmed as a Sales Order in Zoho (ERP) |
| `manifest_date` | First `status=64`, else first `status>64` |
| `dispatch_date` | First `status≥65` |

**Only orders with all three timestamps present are kept** (`HAVING` clause) — this is effectively the eligibility filter: an order must have completed SO → manifest → dispatch within the log window to be counted at all.

### 3. Bulk-order flag (`bulk_check`)
An order is `is_bulk_order = 1` **only if every single line item** in the cart is a drug with `drug_stock IN (1,8)` (i.e., readily-stocked/bulk-inventory SKUs). If even one item needs external procurement, the whole order is non-bulk.

### 4. Carrier normalization
Raw `carrier` string is bucketed into `standard_carrier` (ElasticRun, Mover, Blitz, Delhivery, BlueDart, XpressBees, ShadowFax, DTDC, Other) via case-insensitive `LIKE` matching.

### 5. SLA cutoff windows (`sla_base`, `mdm_sla_so_manifest`)
Joins to a reference table keyed by **warehouse × hour-of-day × day-of-week** to find the applicable SO-processing window. This is the source of the "hourly cutoff" tables on the dashboard (e.g. "Proposed SO to Manifest TAT", "WH Cutoff Clear Time").

- `sla_end_ts` = end of that window (or start-of-next-day if `end_time=0`)
- `ideal_so` = `sla_end_ts` + **1 hour** if bulk order, else + `so_hr` hours (a per-window allowance, presumably reflecting expected procurement time)

### 6. Next courier cutoff (`next_cutoff_calc`)
Looks up `marketplace_courier_cutoff_timetable` (per warehouse × carrier), builds candidate cutoff timestamps for day+0/+1/+2, and picks the **earliest cutoff that is at least 30 minutes after `so_date`**. This is the order's target pickup wave.

### 7. Breach waterfall (strict priority order — an order gets exactly one attribution)

```
is_breach          = next_cutoff + 2h < dispatch_date
is_so_breach       = is_breach AND ideal_so < so_date
is_so_breach_bulk  = is_so_breach AND is_bulk_order = 1
is_manifest_breach = is_breach AND NOT is_so_breach AND next_cutoff < manifest_date
is_dispatch_breach = is_breach AND NOT is_so_breach AND NOT is_manifest_breach
```

Plain English:
- **2-hour grace buffer** is added to the cutoff before anything counts as a miss.
- If the SO itself was confirmed late → **Procurement Miss**.
- Else if manifesting wasn't done by cutoff → **Warehousing Miss**.
- Else (manifested in time, but courier still didn't pick up by cutoff+2h) → **Logistics Miss**.

### 8. Two different date cohorts, unioned together (Q36369 only)
The final aggregation in 36369 unions two groupings and re-sums:
- Orders grouped by **`created_date`** → gives "Total Orders Placed" (pure daily volume)
- Orders grouped by **`ideal_dispatch`** (the target dispatch date) → gives "Total Eligible Orders" / breach counts

**Important subtlety:** "Total Orders Placed" and "Total Eligible Orders" on the dashboard are **not the same order set for a given date** — one is bucketed by creation date, the other by target-dispatch date. An order created late at night might have its eligibility/breach counted against the next day.

---

## Pipeline B — Pharmacy workflow engine (`first_rfd` + `rfd_base`)

**Q39106 → `first_rfd`** (order-level detail, 7-day order window, joins 2 months of logs)
**Q39073 → `rfd_base`** (aggregated by date × warehouse, ~31-day order window, joins 60 days of logs)

This pipeline tracks the **full pharmacy fulfillment funnel** and defines breach differently: against `first_pickup_at` (from `marketplace_order_analytics` — presumably the courier's first pickup attempt), not a fixed cutoff+grace.

### Milestones tracked (order_logs)
`doc_pend_created_at` → `doc_appr_created_at` → `so_date` → `picker_assign` → `picking_comp` → `phar_accept` → `invoiced` → `packed` → `label_generated` → `manifest_date`, compared against `first_pickup_at`.

### Breach flags

**Q39106:**
```
procurement_required_bool = so_date IS NULL ? (now > order_created+15min)
                                             : (so_date > order_created+15min)
doctor_breach_flag        = doc_pend exists AND (doc_appr IS NULL OR doc_appr > doc_pend+30min)
breach_flag                = manifest_date IS NULL OR manifest_date > first_pickup_at
```

**Q39073 (note the threshold differs — see Discrepancies below):**
```
procurement_breach_flag = so_date IS NULL OR so_date >= order_created+20min
doctor_breach_flag      = doc_pend exists AND (doc_appr IS NULL OR doc_appr > doc_pend+30min)
breach_flag              = first_pickup_at IS NOT NULL AND (manifest_date IS NULL OR manifest_date > first_pickup_at)
```

### Root-cause waterfall (same priority pattern as Pipeline A)
```
procurement_breach = breach AND procurement_required
doctor_breach       = breach AND NOT procurement_required AND doctor_breach_flag
manifest_breach     = breach AND NOT procurement_required AND NOT doctor_breach_flag   (catch-all)
```

So: procurement delay is checked first, doctor-approval delay second, and anything else left over is blamed on the warehouse/manifest step.

### Two date cohorts again (Q39073)
Same pattern as Pipeline A — unions orders by `order_created_date` (volume) with orders by `first_pickup_date` (eligibility/breach cohort), then re-aggregates.

---

## Key differences between Pipeline A and Pipeline B (do not compare metrics across them directly)

| | Pipeline A (`OPS_BASE`/`Base_Data`) | Pipeline B (`first_rfd`/`rfd_base`) |
|---|---|---|
| Breach reference point | Courier cutoff time + 2h grace | Actual first pickup attempt (`first_pickup_at`), no grace buffer |
| "Procurement required" definition | Based on actual drug catalog (`drug_stock IN (1,8)`) | Based on how long SO confirmation took (>15 or >20 min) — a **behavioral proxy**, not the actual catalog |
| Warehouses covered | 5 (Blr, Del, Mum, Luc, Kol) | 7–8 (adds Patna, Hyderabad, M-WH) |
| Granularity of workflow | SO → Manifest → Dispatch (3 stages) | Doctor approval → SO → Picking → Pharmacist accept → Invoice → Pack → Label → Manifest (full funnel) |
| Lookback windows | 17 days (36369) / 8 days (36370) | 7 days orders / 2 months logs (39106); 31 days orders / 60 days logs (39073) |

---

## Inconsistencies worth flagging to the team

1. **Procurement-required threshold drift**: Q39106 uses `>15 minutes` past order creation to decide if procurement was required; Q39073 uses `>20 minutes`. These are supposed to be the same underlying definition (one is the order-level version, one the aggregated version) — this looks like version drift/a bug rather than an intentional change, and it means `first_rfd` (order-level) and `rfd_base` (aggregated) could disagree on a given order's classification.

2. **Two unrelated definitions of "procurement required"** exist in the workbook simultaneously: Pipeline A's catalog-based `is_bulk_order` vs Pipeline B's time-based `procurement_required_bool`. The dashboard's "Procurement not required [BULK-(1,8)]" split (from Pipeline A) and Pipeline B's `procurement_breach` numbers are **not measuring the same thing**, even though both get called "procurement."

3. **Grace buffer asymmetry**: Pipeline A gives every order a 2-hour grace past cutoff before flagging a breach; Pipeline B has no such buffer (compares directly to the pickup timestamp). This alone will make Pipeline B's breach rates look structurally stricter/higher than Pipeline A's, independent of actual ops performance.

4. **Different eligibility windows for `is_eligible`/`breach_flag`**: Pipeline B's Q39073 only computes a breach for orders where `first_pickup_at IS NOT NULL`; Q39106 falls back to comparing against `now()` for orders with no pickup yet. So an order still in-flight could be "not yet breached" in one tab and silently excluded in the other, depending on which one you're looking at.

5. **`created_date` uses different logic for `order_creation_flow = 'prescription'`** orders in Pipeline A — it substitutes `odd_created_at` (the order-pending status timestamp) for the raw `created_at`. If a prescription sits in a review queue before that status fires, the SLA clock effectively doesn't start until then — worth confirming this is intentional and not masking review-queue delays.

---

## Core reference tables driving the SLA targets
- `prx_prod_db.mdm_sla_so_manifest` — warehouse × hour × day-of-week SLA window definitions (source of the hourly cutoff/TAT tables)
- `prx_prod_db.marketplace_courier_cutoff_timetable` — per warehouse × carrier daily cutoff times (source of "next cutoff"/dispatch slot logic)
- `prx_prod_db.mdm_master_drug_data` — drug catalog with `drug_stock` codes, used to classify bulk vs non-bulk orders in Pipeline A
- `prx_prod_db.marketplace_order_status_log` — the event-log source for every milestone timestamp in both pipelines
- `prx_prod_db.marketplace_order_analytics` — source of `first_pickup_at`, the anchor for Pipeline B's breach definition
