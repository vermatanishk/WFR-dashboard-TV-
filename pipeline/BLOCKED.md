# Known blockers in this container (2026-11-18 7pm scheduled run)

## This run: 11/14 gates green (up from 9/14 at start) via the two working MCP connectors only

Checked connectors first per the daily-refresh instructions: both worked (`mcp__ClickHouse__get_organizations`
resolved org `PlatinumRx` / service `PRx Nucleus`; `mcp__Zoho_Desk__getOrganizations` returned org 60026539570
on the first call). `pipeline/.zoho.env` is still absent and `cdn.platinumrx.in` is still refused by the agent
proxy (403 Tunnel connection failed, re-tested directly) - both unchanged structural blockers, now 12 scheduled
runs running into them.

- **Returns-pull coverage**: pulled the 4 missing 7-day ClickHouse chunks (`cmp_returns_20261021_20261028` through
  `..._20261111_20261118`) via the ClickHouse MCP, exact query from `build_complaints.py`'s docstring. Coverage
  closed: 2026-08-26..2026-11-18.
- **Core WH-verdict backfill (gate-exact)**: computed the precise todo list from `refresh_all.py`'s own `gates()`
  logic - 27 tickets past T-2 with no cached verdict + 48 stale `no_wh_comment`/`unrecognized` provisional verdicts
  from the last 14 days. Resolved all 75 via the Zoho Desk MCP (`searchTickets` by `ticketNumber`, paired by the
  returned field never by position; `getTicketComments` per ticket, full thread read before classifying), classified
  with the real `classify_wh_comments()` (imported, not hand-guessed). Result: 2 admissions, 24 denials, 45
  `no_wh_comment`, 4 `unrecognized` (all "Not related to our inventory" batch-mismatch denials from Warehouse - no
  admission/denial template match). No BOD-given-after-admission conflicts seen. Both core WH-verdict gates closed.
- **Complaint-baseline WH verdict gap**: after rebuilding `build_complaints.py`, 31 ticketed complaints past T-2 had
  no cached verdict; 27 were already covered by the core backfill above, the remaining 4 (269694, 269738, 269779,
  269788) read live - all `no_wh_comment` (no Warehouse-role comment in any of those threads). Closed the gap (0).
  Re-ran `build_complaints.py` (pass 2) and `cmp_view_spec.py`.
- **EOD tab**: `build_eod_auto.py` for_date 2026-11-16 (27 tickets, 2 accepted - "we have sent short qty to CX" /
  "we have sent wrong sku to CX"). Packer/manifester for the 2 accepted orders (4763708, 4779920) pulled via the
  ClickHouse MCP (`marketplace_order_status_log`, status 52/64) into `zoho_raw90/eod_chain.json`. One accepted
  ticket (269714/4763708, created 2026-11-16) still shows no picker/qc and location Unknown - consistent with the
  documented ClickHouse-ingestion-lag caveat for very recent orders (its return request / scan logs haven't landed
  yet), not the join-backwards bug (the other 26/27 tickets resolve location correctly; isolated to the newest
  tickets only). 7/27 EOD tickets show Unknown location, all the most-recently-created ones in the window - flagging
  per the >10% rule but not treating it as the known join bug given the pattern.
- Ran `build_full_dataset.py` (2620 tickets; `reconciles` holds: wh_accepted 177 + bod 1705 + considered_bod 521 +
  no_return_record 217 = 2620), `build_report.py`, `build_macro_trend.py` (T-2 cap 2026-11-16), `build_html.py`,
  and the full test suite: `test_wh_comment_classifier.py` 89/89 pass; `test_complaints.py` 1 expected failure
  (the photo-backlog check, see blocker below, not a regression); `node test_view_js.js wfr/damage/swap` all green
  (0 diffs across 7434 + 3658 + 12078 cells).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged, now 12 scheduled runs

Still absent in this fresh container. The Zoho Desk MCP connector is unaffected and was used extensively above
(75-ticket WH-verdict backfill + 4-ticket complaint-baseline gap) - the remaining gap is specifically the REST-only
pipeline scripts not replicated via MCP this run (`pull_dependency.py`, `pull_ticket_routing.py`,
`pull_swap_tickets.py`, `pull_swap_routing.py`), which also need blocker #2 below regardless of credentials.

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged, now 12 scheduled runs

Re-confirmed this run with a direct HTTPS request: `CONNECT tunnel failed, response 403`. Did not re-attempt
`update_environment` - needs a person's approval, nobody is present on this unattended run. This blocks:
- The damage-photo backlog (94 orders now "Photo not read yet" within the last 30 days - up from 83 at the start
  of this run, because the complaint baseline advanced from 2026-11-16 to 2026-11-17 and surfaced more damage
  complaints inside the window; expected consequence of a more current baseline, not a new bug).
- Every RCA/swap image read (receipt/batch photos, courier-label swap evidence) - both tabs stay at 2026-11-03.

## For the owner

Same two asks as prior runs, now compounding for the 12th time:
1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set up itself.
   Order swap and RCA exports are now **15 days stale** (through 2026-11-03).
2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now") fixes the
   photo-read backlog permanently for scheduled runs too. 94 damage-complaint photos from the last 30 days are
   waiting on this right now, growing each run as the complaint baseline catches up.

Both fixes are one-time, few-minute actions in an interactive session.
