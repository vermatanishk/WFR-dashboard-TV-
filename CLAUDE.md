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
   - `marketplace_return_request` / `marketplace_return_items` — used only to
     know **whether a return record exists at all** (drives `no_return_record`
     vs. everything else) and the customer-stated `reason`. The request-level
     `remark` field is read from here but is **never used to decide
     wh_accepted/bod/considered_bod** — see "Core classification logic" below
     for why.
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

**Resolution** (per order with a ClickHouse return record) is decided
**entirely by the Warehouse team's own Zoho comment — never the ClickHouse
remark.** This was a major fix (2026-09-21, hardened further on the same
day to remove the remark fallback outright) — see "Warehouse-comment
classifier" below for why the remark can't be trusted at all, even as a
fallback. Logic in `classify()`
([pipeline/build_full_dataset.py](pipeline/build_full_dataset.py)):
1. If `wh_text_check.json` has an `admitted` verdict for this ticket →
   `wh_accepted`, full stop.
2. If it has a `denied` verdict → `bod`, full stop.
3. Anything else — no cache entry yet, `no_wh_comment` (nobody from
   Warehouse ever commented), or `unrecognized` (WH commented but it matched
   neither the admission nor denial pattern) — is `considered_bod`:
   **defaults to BOD but tracked separately** as unconfirmed, never folded
   into `bod`, and **never resolved by looking at the ClickHouse remark**.
- `no_return_record` — no return row at all, excluded from the refund total.

The ClickHouse `remark` field is not read anywhere in this decision. A
`considered_bod` ticket is unconfirmed on purpose — the fix is to backfill
its WH-comment verdict (see below), not to fall back to the remark.

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

**Why this exists, and why there's no remark fallback at all**: investigating
a user report on 2026-09-21, live-checking real `wh_accepted` tickets that
had never been manually spot-checked found ~80% were actually explicit
Warehouse denials (several with the support L2 agent's own note literally
reading "BOD Issued to Customer" right below the denial) that the
ClickHouse-remark-based logic was still crediting to the warehouse. The
remark field tracks "was this refunded," not "whose fault was it" — the
first fix made the WH comment win on conflict, but the remark was still
used as a *fallback* for tickets not yet backfilled, which meant the exact
same failure mode (remark disagrees with reality) was still live for every
uncached ticket. The remark was therefore removed from `classify()`
entirely, same day — a ticket with no WH-comment verdict yet is
`considered_bod` (openly unconfirmed), never silently resolved off the
remark. This makes `wh_accepted`/`bod` **only as complete as the backfill
coverage below**, by design — an honest smaller number beats a larger one
that's silently wrong for every uncovered ticket.

**`pipeline/zoho_raw90/wh_text_check.json`** stores the verdict per
ticket_id: `{"verdict", "evidence", "reason", "order_id", "admitted"}` (the
last one is a legacy bool kept for older tooling). Grows incrementally —
never re-checks a `ticket_id` already present. As of 2026-09-21 the entire
`wh_accepted` bucket (207/207 tickets that were `wh_accepted` at the start
of that backfill) has been live-checked; the `bod`/`considered_bod`
population is still only partially covered (check the cache's entry count
against total tickets with a return record before treating a refresh's
`bod`/`considered_bod` split as final — see caveats below).
**If asked to keep backfilling**: pull the ticket's internal Zoho `id` via
`searchTickets` (batch `ticketNumber` values, up to ~15-20 per call — the
`ticket_id` in our data is Zoho's short `ticketNumber`, NOT the internal
`id` `getTicketComments` needs), fetch its comments, run
`classify_wh_comments()`, append to the cache with the schema above.
Re-run `build_full_dataset.py` after any batch to pick it up.

**EOD tab** (`pipeline/build_eod.py`) is separate and stricter: T-2 tickets
only (2-day lag so WH has time to comment), classified purely by whether a
Warehouse-role Zoho comment contains a genuine admission phrase (e.g. "we
have sent short qty to Cx") vs. a denial template ("We have sent proper
medicine to Cx"). Read the full comment thread before classifying — the
file's dated run-notes document real near-misses (denial-looking text that's
actually neutral, admissions followed by unrelated later BOD notes, etc.).

**Always sync EOD's verdicts into `wh_text_check.json` too** (found missing
on 2026-09-23, backfilled retroactively for one date as a fix). `data_eod.json`
is overwritten fresh each run with only that day's T-2 tickets - the WH-comment
read done for every EOD ticket is real, verified work, but if it's never
copied into `wh_text_check.json` it (a) never benefits Tab 1's numbers, so a
ticket can show a confirmed EOD admission while Tab 1 still shows it
uncached, and (b) gets silently lost the next day when `data_eod.json` is
overwritten. After running `build_eod.py`, add each of that run's tickets to
`wh_text_check.json` too (`admitted` if `wh_accepted_text` is true, `denied`
if it has a comment that isn't an admission, `no_wh_comment` if
`wh_comment` is null) - skip a `ticket_id` already present, same
never-recheck rule as everywhere else.

**Backfill pitfalls (found 2026-10-09 reconciling Tab 1 against 54 days of
EOD history from git; each checked against live Zoho threads):**
- **`no_wh_comment` and `unrecognized` are provisional, not final.** A ticket
  read before WH commented is cached `no_wh_comment` and the "never re-check"
  rule then freezes it. In the EOD overlap, EOD's read disagreed with 33 of
  246 cached `no_wh_comment` verdicts (13%); the 7 where EOD saw an admission
  were re-read in Zoho - 6 real admissions, 1 EOD error (251554). Only `admitted` and
  `denied` are safe to skip on later runs; re-read the other two until the
  ticket is past T-2, and never cache a verdict for a ticket younger than T-2.
- **Pair comments to tickets by `ticketNumber`, never by position.**
  `searchTickets` does NOT return rows in the order of the `ticketNumber`
  list you pass. The 2026-08-17 batch attached evidence text to the wrong
  tickets (253162 and 255197 cached as `admitted` with 253385's admission;
  253385 cached `denied`; 253278 and 257980/257982 also crossed). The EOD
  history has the same failure (253278, 251554 recorded a WH comment that
  doesn't exist on the ticket). A cheap audit: any cached `evidence` that
  differs from the same ticket's EOD `wh_comment` is suspect.
- **Sync EOD verdicts for every run, not one date** (the 2026-09-23 sync only
  covered one date; ~450 EOD-read tickets from 26 Jul - 20 Sep are still
  uncached). Spot-check EOD admissions against the thread before syncing.
- **Tickets with a multi-order or placeholder Order ID never reach Tab 1.**
  `parse_order_id()` drops 82 of 2,460 pulled tickets (e.g. `'3534357 ,
  3781006'`, `N/A`, empty); EOD counts them. Known, deliberate, but it means
  Tab 1 can sit a few admissions below EOD.
- **Day buckets differ:** Tab 1 / macro table bucket by UTC date of
  `created_time`; EOD uses the IST calendar day. A ticket created after
  18:30 UTC lands on different days in the two tabs.

**A confirmed WH admission can still show 0 on Tab 1 if ClickHouse has no
`marketplace_return_request` row for that order yet** - `classify()`
returns `no_return_record` as soon as there's no return row, before it ever
looks at `wh_text_check.json`. This is by design (the `reconciles` invariant
only covers tickets with an actual return/refund on file), not a bug in the
WH-comment logic - but it means a same-day admission can lag behind on Tab 1
by however long ClickHouse takes to ingest the return request, even once
the ticket is correctly cached. If a user reports "X clearly has a WH
admission but Tab 1 shows 0/considered_bod", check `no_return_record` here
before assuming the classifier or cache is wrong.

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
5. `pipeline/build_macro_trend.py` — Tab 1's unfiltered macro trend table
   (Delivered Orders / Return Requested / WH Accepted by category) →
   `macro_trend.json`. **Capped at T-2** (IST date of `data.json`
   `generated_at` minus 2 days, same as the EOD tab) because WH needs ~2 days
   to comment - newer days would show a structurally low WH Accepted. The rest
   of Tab 1 (tiles, charts, ticket list) is not capped, so those totals can
   exceed this table's by `excluded_tickets` (stored in the JSON). Reads delivered-order counts from
   `pipeline/zoho_raw90/ch_delivered_daily.json` (a ClickHouse
   `marketplace_order_status_log` pull, `current_status_id = 70` — see the
   query in the script's docstring) — re-run that query and overwrite the
   file when its date range goes stale.
6. RFD adherence pipeline (see below) → `pipeline/rfd_weekly.json`.
7. `pipeline/build_html.py` — substitutes all the JSON files into
   `pipeline/dashboard.html`'s `__X_JSON__` placeholders, writes
   `pipeline/dashboard_built.html`, copies it to repo-root `index.html`.
8. Commit + push.

## RCA layer (added 2026-10-14) — Tab 6 "RCA"

Per raised ticket: *how the warehouse investigated* (funnel) and *why it happened* (RCA).
Run after step 2, before `build_html.py`:
1. `python3 pipeline/pull_dependency.py` — Zoho `Dependency` custom field (`cf_dependency`) per
   ticket → `zoho_raw90/ticket_dependency.json`. Auth is `pipeline/zoho_auth.py`: credentials in
   `pipeline/.zoho.env` (gitignored; Vercel auto-deploys this repo so secrets must never be committed),
   the 1h access token auto-refreshes into `pipeline/.zoho_token.json`. **Fallback**: if the REST path
   fails, use the Zoho Desk MCP (`searchTickets` by ticketNumber → `cf.cf_dependency`) and write the same
   cache. Incremental; nulls re-fetched until the ticket is 3 days old. `Attribution` is NOT an outcome.
2. Save ClickHouse pulls via MCP (`order_id` never `id`, CDC-dedupe `LIMIT 1 BY id`, drop
   `_peerdb_is_deleted`; do NOT filter `is_active`, it is 0): `rca_expiry_raw.jsonl` (query in the
   `build_rca_inputs.py` docstring) and `rca_return_images_raw.jsonl` (return items, skip reason `RTO`;
   `image_urls` are public `cdn.platinumrx.in` URLs, 1-3 per return item; return-item `drug_code` is the
   ORDERED SKU).
3. `python3 pipeline/rca_images.py` downloads/dedupes images (gitignored `rca_images/`) and writes
   `rca_image_pending.json`. **Read every pending image with vision** (a montage of 2 per sheet works) and
   append to `rca_image_check.json` (schema in the script docstring: unreadable = null, never inferred;
   personal data on invoices/labels is never stored). Key results by the exact `hash` from the pending list.
4. Wrong medicine: save `rca_wrongmed_raw.jsonl` via the ClickHouse MCP (ordered name + bin from
   `mdm_drug_warehouse_locations` at the order's warehouse, best catalog candidate for each received brand;
   query shape in `build_rca_wrongmed.py` docstring), then `python3 pipeline/build_rca_wrongmed.py`. Only the
   received SKU NAME is required; the catalog candidate must be verified from the name read before a bin
   relation is computed (else `candidate_unverified`).
5. `python3 pipeline/build_rca_inputs.py` → `rca_expiry.json`; `python3 pipeline/build_rca.py` → `rca.json`
   (fails loudly if the funnel does not reconcile; T-2 capped).
Tests: `test_wh_comment_classifier.py` (incl. investigation sub-reasons) and `test_rca.py`.

Rules decided with the owner: the funnel is by OUTCOME — Accepted / Rejected / No decision (+ "Not yet
read" = no WH verdict cached, a coverage gap kept separate). `Dependency` is NOT a funnel stage (agents
remove it later; shown informationally). No decision is broken down first-match-wins: footage not
available, batch-not-from-our-inventory claim, CX image not clear (WH said so OR every image on the
return was unreadable to us), dependency not marked (Dependency != Warehouse), then return-not-received,
other WH note, no WH comment. Bin links are attributed as **picking error only** (same bin = strong, same
rack = supporting, same zone+vertical = weak; no "layout error" label; zone `UN` is never a bin). Expiry:
shelf life at **delivery** (status 70), day-1 expiry = end of that month, `<3m` vs `>=3m`; where the
allocation has ≥3 months the next check is the image batch/expiry vs invoice. Image-derived verdicts are
capped at `likely`; no per-field accuracy figure exists yet.

Findings worth knowing (first full read, 2026-10-14, 39 expiry tickets with images): 15 show a received
item whose printed expiry is already before delivery although the allocation looked fine; in 10 the
printed batch differs from the allocated batch and in 7 the batch matches but the stored expiry differs
from the print (stored data vs print). 13 had nothing legible (logo placeholder, corrupted/truncated
uploads, blur). Courier labels in several photos carry a different order id than the ticket.
No-WH-comment tickets (no decision): not agent-markable as Warehouse when another dependency applies,
order COGS < 100 (allocated qty x `zoho_inward_items.rate`, `rca_order_meta.json`), or DocPharma
(warehouse_id 4); otherwise `agent_mistake`.
Owner-confirmed labels live in `pipeline/zoho_raw90/rca_manual_labels.json` (keyed by order_id) and override
the image classifier in `build_rca_wrongmed.py`; owner rule: judge only the SKU in concern (the ordered
return-item SKU), other products in the photo are out of scope. These are the ground truth for any accuracy
measurement of the image reads.
**Re-read provisional WH verdicts every refresh** (`python3 pipeline/recheck_wh_comments.py`): cached
`no_wh_comment` / `unrecognized` are re-read live (and uncached tickets read) before `build_full_dataset.py`;
`admitted`/`denied` are final. Found 2026-10-14: 1,135 of 1,412 provisional/uncached verdicts changed,
e.g. 233123 (admission) and 250676 (denial) were stuck as no_wh_comment. The script stores `subtype`
(footage / batch / image reason) and `wh_texts` per ticket - the no-decision sub-reason is read from EVERY WH
comment, not from the admission/denial evidence (neutral-only threads have none). Owner-confirmed admissions:
MRP mismatch, missing/not-mentioned free item, packer did not remove medicine outside, expiry/excess/wrong
free item sent.
Other branches (`pipeline/build_rca_extra.py` -> `rca_extra.json`, run before `build_rca.py`; inputs saved from
the ClickHouse MCP): Missing/short qty = ONLY the tree's split (SKU missing vs item missing, from the return item); pick scans are
deliberately NOT used as evidence (owner: a scan can be logged for a pick that never physically happened).
Damaged = cold flag (`is_cold`) +
logistics exception (`shipment_events` ndr_count / ofd_count, `shipment_latest.delivery_attempts`;
`rca_logistics.json`); no logistics exception stays *undetermined*, never WH. Swap = courier label order id
mismatch (image) - no shared AWBs found (`rca_swap.json`). "Order not placed by customer" is deliberately OUT of
scope (owner, 2026-10-14: low volume, not a WFR aspect). MRP/Batch Mismatch is mapped in
`CATEGORY_MAP` ("MRP/Batch Mismatch", "MRP Mismatch"); tickets only exist after the next ticket pull - until then
`rca_mrp_sample_reads.json` holds a hand-read sample. Return status codes: `marketplace_status_master`
(280 cancelledReturn, 231 returnPickupCancelled, 250 ItemQualityCheckAtOurFacility).
Damaged flow (owner, 2026-10-14): 1) cold / non-cold from the drug flag, 2) images are read ONLY for non-cold
(cold = temperature complaint, never image-read; also note drug flag vs complaint reason can disagree - 3 "Issue
with cold storage" tickets sit on drugs flagged non-cold), 3) each complained line gets exactly one classifier
bucket from `pipeline/damaged_buckets.py` (8 buckets; wrong-item-in-photo and logo-only fold into "Image not
relevant"). Read results: `zoho_raw90/rca_damaged_noncold.json`.
Known gaps: ~45% of tickets are "Not yet read"; no structured received-SKU/batch field in Zoho
(`Incorrect Batch received` etc. are always empty); damaged/short-qty/order-swap RCA not built.

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
  backfill coverage** — `classify()` has no remark fallback at all, so any
  ticket without a cached `admitted`/`denied` verdict sits in
  `considered_bod` until it's checked, growing incrementally (check
  `wh_text_check.json`'s entry count against total tickets with a return
  record before treating a refresh's `wh_accepted`/`bod`/`considered_bod`
  split as fully verified). The `wh_accepted` bucket was fully backfilled
  on 2026-09-21; `bod`/`considered_bod` were not — a large `considered_bod`
  count is expected and correct until that backfill catches up, not a bug.
- `considered_bod` is a default-when-ambiguous bucket, not a confirmed
  classification — always show it as its own line, never merge into `bod`.
- Personnel leaderboards should stay **rate-based** (errors / total
  throughput), not raw counts — raw counts unfairly penalize high-volume
  staff. Track the unattributed % explicitly rather than dropping it.
- `Mis-shipment_Dashboard_Requirements.md` is the original spec and is now
  stale in places (it lists the warehouse-location mapping and picker/QC
  ledger as unresolved — both are solved in the current code). Treat it as
  historical context, not current status.
