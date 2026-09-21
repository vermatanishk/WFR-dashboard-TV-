# WFR (Wrong Fulfillment / Mis-shipment) Dashboard — Project Context

Read this before doing anything in this repo. It exists so a fresh Claude Code
session doesn't need to be re-briefed every run.

## What this is

A daily-refreshing ops dashboard for PlatinumRX warehouses, consolidating
**mis-shipment tickets** (wrong item, missing/short qty, expired, damaged,
switched order) across all warehouses, with a specific focus on: which
mistakes the warehouse **accepted** (admitted fault) vs. which were resolved
as **benefit of doubt (BOD)** to the customer without a confirmed WH-fault
admission.

Live output: `index.html` at repo root, served by Vercel at whatever domain
is linked to `vermatanishk/WFR-dashboard-TV-` (auto-deploys on push to
`main` — no CI config needed, just Vercel's git integration).

## How this repo gets refreshed — READ THIS FIRST

**There is no cron job, scheduled task, or GitHub Action.** The "routine" is
a Claude Code session (this kind of session) that periodically:
1. Pulls fresh data from Zoho Desk + ClickHouse via MCP.
2. Runs the pipeline scripts below.
3. Commits progress in checkpointed `WIP: ...` commits (data pulls are
   chunked/rate-limited, so commit after each stage rather than losing work).
4. Finishes with a `Refresh <date> <time> IST` commit and pushes to `main`.

If asked to "run the daily refresh" / "refresh the dashboard", that means:
re-pull the data, re-run the pipeline (see order below), rebuild the HTML,
commit incrementally, push. Check git log for the most recent refresh commit
to know how stale the current data is before starting.

## Data sources (via MCP)

1. **Zoho Desk** — ticket-level: `Ticket Id`, `Order ID`, `Created Time`,
   `Dispositions`/`Sub-disposition`, `Status`, `Team`, comment threads.
2. **ClickHouse `prx_prod_db`**:
   - `marketplace_return_request` / `marketplace_return_items` — return
     reason (customer-stated) + remark (WH-confirmation text).
   - Scan logs (picker `scanned_by_user_id` + pick counts, QC checker) for
     personnel attribution.
   - `marketplace_orders` — warehouse_id → location. **Join on `order_id`,
     NOT `id`** — these two columns diverge and joining on the wrong one
     silently returns wrong/Unknown locations for most orders (this broke
     every location in the EOD tab until 2026-08-01 — see the note in
     `pipeline/build_eod.py`).
   - `mdm_master_drug_data` / `marketplace_order_item_batches` — cold-chain
     flag per order.

## Core classification logic (the heart of the project)

Full detail: [Mis-shipment_Dashboard_Requirements.md](Mis-shipment_Dashboard_Requirements.md),
[pipeline/category_mapping.py](pipeline/category_mapping.py).

**Category** — raw messy Zoho `Sub-disposition` text → one of 5 canonical
categories via `CATEGORY_MAP` (Missing/Wrong Qty, Wrong Medicines, Expiry
Issue, Damaged/Defective, Switch Orders). Extend the dict when new free-text
variants show up.

**Resolution** (per order with a ClickHouse return record) is decided by the
**Warehouse team's own Zoho comment first**, not the ClickHouse remark. This
was a major fix (2026-09-21) — see "Warehouse-comment classifier" below for
why the remark can't be trusted alone. Priority in `classify()`
([pipeline/build_full_dataset.py](pipeline/build_full_dataset.py)):
1. If `wh_text_check.json` has a `denied`/`admitted` verdict for this ticket
   → that decides it outright (`bod`/`wh_accepted`), full stop, regardless
   of what the ClickHouse remark says.
2. Otherwise (no cache entry yet, or verdict is `no_wh_comment`/
   `unrecognized`) → fall back to the ClickHouse remark patterns:
   - `wh_accepted` — remark matches `WH_FAULT_CONFIRMED_REMARK_PATTERNS`.
   - `bod` — remark matches `NON_WH_FAULT_REMARK_PATTERNS`.
   - `considered_bod` — remark ambiguous/empty and no WH-comment verdict
     available → **defaults to BOD but tracked separately** as unconfirmed,
     never folded into `bod`.
- `no_return_record` — no return row at all, excluded from the refund total.

By construction: `wh_accepted + bod + considered_bod == total returns
issued` — this is checked explicitly (`reconciles` flag in
`pipeline/build_report.py`). If it's ever `False`, something in the
classification logic broke — investigate before shipping a refresh.

### Warehouse-comment classifier (the real source of truth)

[pipeline/wh_comment_classifier.py](pipeline/wh_comment_classifier.py) reads
a ticket's Warehouse-role ("roleName" starting with "Warehouse") Zoho
comments and returns a verdict: `admitted` (genuine first-person fault
admission, e.g. "we have sent wrong sku/short qty to Cx"), `denied` (the
stock-denial template, "We have sent proper medicine to Cx", plus expiry/
cold-chain/batch variants), `no_wh_comment` (nobody from Warehouse ever
commented), or `unrecognized` (WH commented but it's neither template —
footage-not-found, a duplicate-ticket note, etc. — flagged for manual
review, never guessed). Test fixtures for every known trap case (a request
for evidence containing an admission-looking substring, a denial-then-
later-admission thread, batch-disclaim notes, etc.) live in
[pipeline/test_wh_comment_classifier.py](pipeline/test_wh_comment_classifier.py)
— run it after touching either phrase table; every fixture must pass.

**Why this exists**: investigating a user report on 2026-09-21, live-
checking real `wh_accepted` tickets that had never been manually
spot-checked found ~80% were actually explicit Warehouse denials (several
with the support L2 agent's own note literally reading "BOD Issued to
Customer" right below the denial) that the ClickHouse-remark-based logic
was still crediting to the warehouse. The remark field tracks "was this
refunded," not "whose fault was it" — it cannot be trusted as sole ground
truth, ever, for any ticket that hasn't had its actual WH comment read.

**`pipeline/zoho_raw90/wh_text_check.json`** stores the verdict per
ticket_id: `{"verdict", "evidence", "reason", "order_id", "admitted"}` (the
last one is a legacy bool kept for older tooling). Grows incrementally —
never re-checks a `ticket_id` already present. As of 2026-09-21 it covers
~833 of ~2200 tickets with a return record (backfill is ongoing, same
incremental pattern as everything else in this pipeline — prioritize
`wh_accepted` tickets first since a wrong credit to the warehouse is the
costlier error). **If asked to keep backfilling**: pull the ticket's
internal Zoho `id` via `searchTickets` (batch `ticketNumber` values, up to
~15-20 per call — the `ticket_id` in our data is Zoho's short
`ticketNumber`, NOT the internal `id` `getTicketComments` needs), fetch its
comments, run `classify_wh_comments()`, append to the cache with the schema
above. Re-run `build_full_dataset.py` after any batch to pick it up.

**EOD tab** (`pipeline/build_eod.py`) is separate and stricter: T-2 tickets
only (2-day lag so WH has time to comment), classified purely by whether a
Warehouse-role Zoho comment contains a genuine admission phrase (e.g. "we
have sent short qty to Cx") vs. a denial template ("We have sent proper
medicine to Cx"). Read the full comment thread before classifying — the
file's dated run-notes document real near-misses (denial-looking text that's
actually neutral, admissions followed by unrelated later BOD notes, etc.).

## Pipeline execution order

1. Pull/refresh raw data into `pipeline/zoho_raw90/` (Zoho tickets, ClickHouse
   returns/pickers/QC chunks, cold-chain flags, user↔warehouse map).
2. `pipeline/build_full_dataset.py` — joins everything, classifies every
   ticket, writes `data.json` (per-ticket detail), `personnel.json`
   (per-warehouse picker/QC leaderboards, sorted by error **rate** not raw
   count), `trend.json` (daily raised-vs-accepted series).
3. `pipeline/build_report.py` — aggregates `data.json` → `aggregates.json`
   (Tab 1/Tab 2 rollups) + `pipeline/wfr_daily_report.csv` (downloadable).
4. `pipeline/build_eod.py` — separate T-2 text-admission tab → `data_eod.json`.
5. RFD adherence pipeline (see below) → `pipeline/rfd_weekly.json`.
6. `pipeline/build_html.py` — substitutes all the JSON files into
   `pipeline/dashboard.html`'s `__X_JSON__` placeholders, writes
   `pipeline/dashboard_built.html`, copies it to repo-root `index.html`.
7. Commit + push.

## RFD (Rate of First Dispatch) adherence — separate sub-project

Full detail: [RFD_Adherence_Logic_Documentation.md](RFD_Adherence_Logic_Documentation.md).

Two independent ClickHouse breach-detection pipelines exist historically
(cutoff/SLA-based "Pipeline A" vs. pharmacy-workflow-based "Pipeline B") with
different breach definitions, warehouse coverage, and even a same-metric-
computed-two-ways bug (15min vs 20min procurement-required threshold) — **do
not compare their numbers directly**. Recent work (see commits `ed904b3`,
`c1285ed`, `cbb1414`) reconciled the dashboard's leaderboard to match the
live "Master FDR Dashboard" definition exactly and standardized on "RFD"
terminology (drop "FDR" everywhere user-facing). If asked to touch RFD logic,
read that doc first — it's easy to silently reintroduce the discrepancies it
documents.

## Known caveats to keep surfacing, not hide

- **`wh_accepted`/`bod` counts are only as reliable as the WH-comment
  backfill coverage** (~38% as of 2026-09-21, growing incrementally — check
  `wh_text_check.json`'s entry count against total tickets with a return
  record before treating a refresh's numbers as fully verified). Any ticket
  still on the ClickHouse-remark fallback carries the same risk the
  2026-09-21 fix uncovered — don't assume it's fixed just because the code
  is; check coverage.
- `considered_bod` is a default-when-ambiguous bucket, not a confirmed
  classification — always show it as its own line, never merge into `bod`.
- Personnel leaderboards should stay **rate-based** (errors / total
  throughput), not raw counts — raw counts unfairly penalize high-volume
  staff. Track the unattributed % explicitly rather than dropping it.
- `Mis-shipment_Dashboard_Requirements.md` is the original spec and is now
  stale in places (it lists the warehouse-location mapping and picker/QC
  ledger as unresolved — both are solved in the current code). Treat it as
  historical context, not current status.
