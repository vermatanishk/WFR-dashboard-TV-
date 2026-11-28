# Known blockers in this container (2026-11-28 7pm scheduled run)

## This run: 17/24 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked (ClickHouse org PlatinumRx, Zoho org 60026539570). `pipeline/.zoho.env` is
still absent, so every REST-only script fails immediately - same as every recent unattended run.
Work done this run:

- ClickHouse returns pull: the 4 incremental 7-day chunks `refresh_all.py plan` listed (31 Oct - 28
  Nov), closing the "returns pull covers through yesterday" gate.
- Core WH verdicts: the 23 tickets past T-2 with no cached verdict, plus 7 more baseline-only gap
  tickets surfaced by `build_complaints.py`, were all read live via the Zoho Desk MCP fallback
  (`searchTickets` by ticketNumber -> `getTicketComments`, paired by ticketNumber as always) and
  classified with the real `wh_comment_classifier` logic via `ingest_wh.py`: 15 denied, 15
  no_wh_comment, 0 new admissions this run (every Warehouse comment read was the stock "We have
  sent proper medicine to CX" denial template).
- Downloaded the "Pan India errors sheets" Google Sheet via the Drive MCP (`wh_error_log.py <csv>`):
  7 new rows, applied to the verdict cache (0 newly flipped to admitted - all were already covered).
- `build_eod_auto.py`: 1 order (4916284) was missing its packer/manifester status-log rows; pulled
  via ClickHouse (`current_status_id IN (52,64)`) and added to `zoho_raw90/eod_chain.json`.
- WFR root-cause inputs (the funnel's root-cause sub-trees, added 2026-11-27): pulled ClickHouse
  inputs for every Missing/short-qty (26 orders total across two passes) and Expiry (6 orders)
  complaint that was "Inputs pending" in the 60-day window - return-item lines
  (`marketplace_return_items` x `marketplace_return_request` x `mdm_master_drug_data`), GRN
  signature rows (`mdm_grn_po_deltas`, marked `checked_codes` even where no inward-pack-confusion
  row existed), and batch-allocation/expiry rows (`marketplace_order_item_batches` +
  `mdm_warehouse_batch_inventory`). `test_wfr_rca.py` now passes clean for both types; only
  Wrong-medicine (10 orders, needs photo reads) is still pending, see blocker #2 below.
- Ran the full local (non-REST) build/RCA/swap/complaints chain: `build_full_dataset`, `build_report`,
  `build_eod_auto`, `build_complaints` (two passes), `cmp_view_spec`, the RCA chain
  (`build_rca_wrongmed/inputs/extra/build_rca`, `build_item_missing_tags` - needed `python3.13`
  explicitly, this container's default `python3` has no pandas/openpyxl), `build_rca_export/trend`,
  `build_swap`, `swap_view_spec`, `archive_exports`, `build_html`, and the full test suite
  (`test_wh_comment_classifier`, `test_rca`, `test_rca_trend`, `test_complaints`, `test_wfr_rca`,
  `test_view_js.js wfr|damage|swap`, `check_view_from_export.py`) - all green except the two photo-
  backlog checks below (expected, structural).
- `pull_ticket_routing.py`, `pull_dependency.py`, `recheck_wh_comments.py`, `pull_swap_tickets.py`,
  `pull_swap_routing.py`, `read_swap_wh.py`, `scan_pack_text.py`, `check_complaints_live.py`: all
  REST-only, skipped (no `.zoho.env`). `wh_text_check.json`'s cache already has 0 hard gaps
  (gate green), so nothing this skip touches is a correctness gap today, only thoroughness.

Gates still red, same 3 structural causes as every recent run (see below): damage/RCA photos
(network), RCA item-missing tags (workbook), Zoho Desk REST access. `sanity_check.py` fails the same
3 checks, all tracing to those causes.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks `pull_dependency.py`, `pull_ticket_routing.py` (effectively), `pull_swap_tickets.py`,
`pull_swap_routing.py`, `scan_pack_text.py`, `check_complaints_live.py`, and the full-backlog
WH-comment recheck (`recheck_wh_comments.py`). The MCP fallback (`searchTickets` + per-ticket
`getTicketComments`) works but costs roughly one tool round-trip per ticket, so it only scales to
the handful of tickets a gate actually requires (today: 30 tickets across the core/baseline gaps),
not the full backlog.

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request (connection reset, no response). Blocks:
- 25 damage/RCA complaint rows "Photo not read yet" in the sanity window (ClickHouse image-URL pull
  works fine, only the image *download* is blocked).
- Every RCA image read (expiry/wrong-medicine/damage photo evidence) - this is also why the 10
  Wrong-medicine WFR root-cause complaints stay "Inputs pending": their cut needs a photo read of
  the received product before the LASA/family/different classification can run.
- The 1 residual swap case (4923220) that needs an image check to pair.

An unattended run cannot get live approval for `update_environment`, so this needs the owner to add
the host once from an interactive session (see "For the owner" below).

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` still does not exist in this container, so
the 25 orders flagged "Tags pending" in the T-2 window cannot be tagged. Manual-pull input per
CLAUDE.md, not something a session can regenerate itself.

## For the owner

Same three structural asks as every recent run:
1. **Zoho REST**: a persistence mechanism for `pipeline/.zoho.env` in the unattended container, or
   re-running the daily refresh from an interactive session periodically to close the REST-only gaps.
2. **Network**: start this routine with "Run now" once and approve the `cdn.platinumrx.in`
   allowlist prompt when it's shown interactively (or add the host in environment settings
   directly) - fixes the photo-read backlog permanently for every future scheduled run too.
3. The pack-mapping workbook needs to live somewhere this container can read it (committed
   gitignored, or re-uploaded each interactive session) for item-missing tagging to run unattended.

All three are one-time or few-minute actions in an interactive session.
