# Known blockers in this container (2026-11-17 7pm scheduled run)

## 0. THIS RUN (2026-11-17): both connectors worked - core + complaint baseline fully refreshed; damage-photos/swap/RCA still blocked

Checked connectors first per the daily-refresh instructions: both worked (`mcp__ClickHouse__get_organizations` resolved
org `PlatinumRx` / service `PRx Nucleus`; `mcp__Zoho_Desk__searchTickets` returned a real ticket on the first call).
`pipeline/.zoho.env` is still absent and `cdn.platinumrx.in` is still refused by the agent proxy (403 Tunnel connection
failed, re-tested directly) - both unchanged structural blockers, now 11 scheduled runs. Gates: 11/14 green (up from
9/14 at the start of this run) via the two working MCP connectors only, with no REST/image access anywhere:

- **Core WH verdict backfill (gate-exact)**: computed the precise todo list using `refresh_all.py`'s own `gates()` logic
  (not an approximation) - 7 tickets past T-2 with no cached verdict + 22 stale `no_wh_comment`/`unrecognized`
  provisional verdicts from the last 14 days. Resolved all 29 via the Zoho Desk MCP (`searchTickets` by `ticketNumber`,
  paired by the returned field never by position; `getTicketComments` per ticket), classified with the real
  `classify_wh_comments()` (imported, not hand-guessed). Result: 3 denials, 2 `unrecognized` (footage-not-found /
  undetermined batch note), 24 confirmed `no_wh_comment`. Both core WH-verdict gates closed.
- **EOD tab**: `build_eod_auto.py` for_date 2026-11-15 (7 tickets, 0 accepted - all denied/no_wh_comment this day).
- **Returns-pull gap (complaint baseline)**: pulled the 4 missing 7-day ClickHouse chunks (`cmp_returns_20261020_20261027`
  through `..._20261110_20261117`, ~26,000 rows total) via the ClickHouse MCP, exact query from `build_complaints.py`'s
  docstring (fixed a column-alias collision from the `x.*`-style SELECT - aliased every column explicitly so the saved
  JSON keys matched `order_id` literally, not `x.order_id`). Coverage closed: 2026-08-26..2026-11-17.
- **New WFR ticket pull**: 31 new tickets (23 "Missing or less quantity received" + 8 "Wrong item Delivered"; the other
  3 sub-dispositions had zero new tickets) via the Zoho Desk MCP, merged into `consolidated.json` (29 unique orders after
  de-dupe). ClickHouse joins for those 29 orders saved as `ch_returns_c8.jsonl` / `ch_pickers_c8.jsonl` / `ch_qc_c8.jsonl`
  (26 of 29 orders already had a `marketplace_return_request` row - the other 3 are `no_return_record`, expected
  ClickHouse-ingestion lag for orders 1-2 days old). Cold-chain flags for all 29 added to `order_cold_flag.json` (all
  non-cold). One missing picker/QC name (`22574`) resolved via `auth_internal_users` and added to `user_names.json`.
- **Orders-volume denominators**: extended `orders_by_day.json` / `orders_by_day_location.json` / `ch_delivered_daily.json`
  through 2026-11-16 with the exact queries in CLAUDE.md step 4 (JOIN on `order_id`, not `id`).
- **Complaint baseline Zoho pull (previously blocked, done via MCP this run instead of REST)**: `pull_complaint_tickets.py`
  is REST-only with no working MCP fallback in code (crashes on `get_token()` before any fallback path), so it could not
  run directly. Replicated its exact logic (same day-window/staleness rule, same per-ticket field extraction, same output
  schema) using the Zoho Desk MCP `searchTickets` with `createdTimeRange` only (no disposition filter - this pull is
  ALL dispositions) for the 8 days the script's own rule flagged as needing a (re-)pull: 2026-11-10 (stale, pulled only
  1 day after it ended), 2026-11-11 (pulled same day), and 2026-11-12 through 2026-11-17 (missing/last-3-days rule).
  ~1,450 tickets pulled, paginated 100/page, verified every page's `createdTime` matched the expected day before merging.
  Closed the "zoho complaint tickets" gate (pulled 2026-11-11 -> 2026-11-17).
- **Complaint-baseline WH verdict gap**: after the above pull, `build_complaints.py` flagged 28 ticketed complaints past
  T-2 with no cached verdict. Read all 28 live via the Zoho Desk MCP (same ticketNumber-pairing + full-thread-read
  discipline as the core backfill) - 1 denial (268719, "We have sent proper medicine to Cx"), 27 `no_wh_comment` (no
  Warehouse-role comment in any of those threads, only L2/Logistics/Manager notes). Closed the "WH verdict gaps" gate (0).
  Re-ran `build_complaints.py` (pass 2) and `cmp_view_spec.py` to pick up the fresh verdicts into the WFR/damage/swap
  trends and the Summary tab.
- Ran `build_full_dataset.py` (2620 tickets; `reconciles` holds: wh_accepted 176 + bod 1686 + considered_bod 541 +
  no_return_record 217 = 2620), `build_report.py`, `build_macro_trend.py` (T-2 cap 2026-11-15), `build_html.py`, and the
  WH-classifier + complaints test suites (`test_wh_comment_classifier.py` 89/89 pass; `test_complaints.py` 1 expected
  failure - the photo-backlog check, see blocker #2 below, not a regression).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged, now 11 scheduled runs

Still absent in this fresh container (`ls pipeline/.zoho.env` -> No such file). The Zoho Desk MCP connector is unaffected
and was used extensively above (including a full hand-rolled replication of `pull_complaint_tickets.py`'s all-dispositions
pull) - the remaining gap is specifically the REST-only pipeline scripts that this run did NOT attempt to replicate via
MCP, because they also require blocker #2 (image reads) regardless of credentials:
- `pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `pull_swap_routing.py`, `recheck_wh_comments.py`'s
  bulk REST path - needed for the RCA/swap exports, which also need `rca_images.py` / `damage_images.py` image reads
  (blocker #2) regardless, so replicating just the ticket-field pulls would not unblock those tabs on its own this run.

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged, now 11 scheduled runs

Re-confirmed this run with a direct HTTPS request: `CONNECT tunnel failed, response 403` (agent-proxy: connect_rejected,
host not allowed for this session). Did not re-attempt `update_environment` - already tried and correctly refused on
multiple prior scheduled runs (needs a person's approval, nobody is present on this unattended run). This blocks:
- The damage-photo backlog (83 orders now "Photo not read yet" within the last 30 days - up from 18 at the start of this
  run, because the complaint baseline advanced from 2026-11-11 to 2026-11-16 and surfaced more damage complaints inside
  the window; this is a direct, expected consequence of the baseline being more current, not a new bug).
- Every RCA/swap image read (receipt/batch photos, courier-label swap evidence) - both tabs stay at 2026-11-03.

## For the owner

- Same two asks as prior runs, now compounding:
  1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set up itself (a
     3-legged OAuth refresh token, not a single API key `request_credential` can inject). Order swap and RCA exports are
     now **14 days stale** (through 2026-11-03).
  2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now") fixes the
     photo-read backlog permanently for scheduled runs too - this is a personal-environment-wide setting, so it would
     stick across both interactive and scheduled containers. 83 damage-complaint photos from the last 30 days are
     waiting on this right now, growing as the complaint baseline catches up each run.
- Both fixes are one-time, few-minute actions in an interactive session - flagging again via push notification in case
  commit messages aren't being seen.
