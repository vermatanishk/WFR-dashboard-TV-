# Known blockers in this container (2026-11-26 7pm scheduled run)

## This run: 17/24 gates green via the ClickHouse + Zoho Desk MCP connectors only

Both connectors worked (ClickHouse org PlatinumRx, Zoho org 60026539570). `pipeline/.zoho.env` is
still absent, so every REST-only script fails immediately - same as every recent unattended run.
Work done this run:

- ClickHouse returns pull: 4 trailing-28-day chunks (29 Oct - 26 Nov), closing the "returns pull
  covers through yesterday" gate.
- Rebuilt `build_complaints.py` on the fresh returns data (WH verdict gaps closed to 0 immediately -
  no new gaps this time).
- Re-read the 17 "provisional verdicts not re-read since yesterday" tickets via the Zoho Desk MCP
  fallback (searchTickets by ticketNumber, paired by ticketNumber not position, full thread read
  before concluding): 14 `no_wh_comment`, 3 `unrecognized` ("Footage attached on dto tool" / "Not
  related to our inventory" x2 - neutral per the classifier's NEUTRAL_PHRASES table, not a denial).
- Extended the core 90-day ticket pull for 2 UTC days the core dataset was missing (2026-11-24,
  2026-11-25 - 59 + 38 "Return and Pickup" tickets via `searchTickets customField1`), merged into
  `cmp_zoho_tickets.json` (`ingest_tickets.py`) and `consolidated.json` (`extend_consolidated.py`,
  +44 tickets). Pulled the 4 ClickHouse joins (returns/pickers/QC/cold-flag) for the 43 newly
  reachable orders as `ch_*_c13.jsonl` + `order_cold_flag.json` merge - `add_core_chunk.py`'s
  expected input files couldn't be built from an auto-saved MCP result this time (all 4 queries
  returned inline, under the auto-save threshold), so the chunk files were written directly from
  the inline query results instead of going through that script.
- Read all 28 Warehouse-role comment threads for the EOD T-2 day (2026-11-24) via the same MCP
  fallback: 1 genuine admission (271062/order 4897150, "we hsbe sent Short qty to cx" - sic),
  24 denials ("We have sent proper medicine to cx/CX" template, 3 different WH agents' phrasing),
  3 no-comment. Pulled the packer/manifester chain for the 1 admitted order and added it to
  `eod_chain.json` by hand (same reasoning as above - small inline result, not auto-saved).
- Rebuilt `build_full_dataset.py` -> `build_report.py` -> `build_eod_auto.py` ->
  `build_macro_trend.py` -> `build_complaints.py` -> `cmp_view_spec.py` -> `archive_exports.py` ->
  `build_html.py`. Core dataset now reaches 2026-11-25 (was 2026-11-23), EOD reaches T-2
  (2026-11-24, was frozen on 2026-11-23).
- All test suites green except the one expected structural failure: `test_complaints.py`'s damage
  photo-backlog check (33/43 "Photo not read yet" rows - see blocker #2 below, unchanged from
  recent runs). `test_wh_comment_classifier.py` 99/99, `test_rca.py` 17/17,
  `node test_view_js.js` (plain + wfr/damage/swap) all 0 differences, `check_view_from_export.py`
  0 mismatches.

Gates still red, same 3 structural causes as every recent run (see below): damage photos (network),
RCA/swap exports + Zoho Desk access gate (REST), RCA item-missing tags (workbook). `sanity_check.py`
fails the same 6 checks, all tracing to those 3 causes - nothing new.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent. Blocks `pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`,
`pull_swap_routing.py`, `pull_complaint_tickets.py`'s bulk/full-range mode, and
`fetch_swap_images.py`. `rca_export.json` and `swap_export.json` are both still capped at
`t2_cap_date` 2026-11-20 (6 days stale now) - advancing them needs the Dependency field and routing
tags for every new ticket since then, which only the REST path pulls in bulk; doing it ticket-by-
ticket through the MCP fallback for this many tickets is out of a single day's token budget (this
run already used a meaningful chunk of budget doing the equivalent for the core dataset + EOD + 17
provisional re-reads - about 45 single-ticket MCP reads total).

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. Blocks:
- 33-43 damage/RCA complaint rows "Photo not read yet" in the sanity window (ClickHouse image-URL
  pull works fine, only the image *download* is blocked).
- Every RCA image read (expiry/wrong-medicine/damage photo evidence).
- The 2 residual swap cases (4800881, 4895817) that need an image check to pair.

An unattended run cannot get live approval for `update_environment`, so this needs the owner to add
the host once from an interactive session (see "For the owner" below).

## 3. RCA item-missing tags: pack-mapping workbook not in this container

`~/Downloads/Pack Quantity & Base Value Changes*.xlsx` still does not exist in this container, so
the 30 orders flagged "Tags pending" in the T-2 window cannot be tagged. Manual-pull input per
CLAUDE.md, not something a session can regenerate itself.

## For the owner

Same three structural asks as every recent run:
1. **Zoho REST**: a persistence mechanism for `pipeline/.zoho.env` in the unattended container, or
   re-running the daily refresh from an interactive session periodically to close the REST-only gaps
   (RCA/swap exports are now 6 days behind the core dashboard and falling further behind each day
   this stays unattended).
2. **Network**: start this routine with "Run now" once and approve the `cdn.platinumrx.in`
   allowlist prompt when it's shown interactively (or add the host in environment settings
   directly) - fixes the photo-read backlog permanently for every future scheduled run too.
3. The pack-mapping workbook needs to live somewhere this container can read it (committed
   gitignored, or re-uploaded each interactive session) for item-missing tagging to run unattended.

All three are one-time or few-minute actions in an interactive session.
