# Known blockers in this container (2026-11-19 7pm scheduled run)

## This run: 11/14 gates green via the two working MCP connectors only

Checked connectors first per the daily-refresh instructions: both worked (`mcp__ClickHouse__get_organizations`
resolved org `PlatinumRx` / service `PRx Nucleus`; `mcp__Zoho_Desk__getOrganizations` returned org 60026539570
on the first call). `pipeline/.zoho.env` is still absent and `cdn.platinumrx.in` is still refused by the agent
proxy (403 Tunnel connection failed, re-tested directly) - both unchanged structural blockers, now 13 scheduled
runs running into them.

- **Housekeeping**: on start, the local checkout was in a detached-HEAD state 5 commits ahead of `main` (the
  2026-11-18 run's commits had pushed to `origin/main` fine, but the session ended before fast-forwarding its own
  branch pointer). Fast-forwarded `main` to match - no data was lost, `git push` confirmed `origin/main` already
  held everything.
- **Returns-pull coverage**: pulled the 4 due 7-day ClickHouse chunks (`cmp_returns_20261022_20261029` through
  `..._20261112_20261119`, the trailing-28-day re-pull window) via the ClickHouse MCP, exact query from
  `build_complaints.py`'s docstring. Coverage closed: 2026-08-26..2026-11-19.
- **Core WH-verdict backfill (gate-exact)**: computed the precise todo list from `refresh_all.py`'s own `gates()`
  logic - 28 tickets past T-2 with no cached verdict + 15 stale `no_wh_comment`/`unrecognized` provisional verdicts
  from the last 14 days. Resolved all 43 via the Zoho Desk MCP (`searchTickets` by `ticketNumber`, paired by the
  returned field never by position; `getTicketComments` per ticket, full thread read before classifying), classified
  with the real `classify_wh_comments()` (imported, not hand-guessed). Result: 2 admissions (269873 "we have sent
  short qty to CX"; 269829 - WH denied first with the stock template, then admitted "we have sent wrong sku to CX"
  2.5 hours later on the same ticket, later comment correctly overrides per the classifier's full-thread rule), 29
  denials, 10 `no_wh_comment`, 2 `unrecognized` (269860 "Not related to our inventory" - no admission/denial
  template match, same known pattern as prior runs; 269618 "Footage not found because it's old order" - neutral
  phrase, no verdict). Both core WH-verdict gates closed.
- **Complaint-baseline WH verdict gap**: after rebuilding `build_complaints.py`, 1 ticketed complaint past T-2 had
  no cached verdict (269856, order 4699253, cold-storage damage complaint) - read live via the MCP, no Warehouse-
  role comment on the thread, cached `no_wh_comment`. Gap closed (0). Re-ran `build_complaints.py` (pass 2) and
  `cmp_view_spec.py`.
- **EOD tab**: `build_eod_auto.py` for_date 2026-11-17 (28 tickets, 2 accepted - the same two admissions above,
  orders 4791536/4746805). Packer/manifester for both pulled via the ClickHouse MCP (`marketplace_order_status_log`,
  status 52/64) into `zoho_raw90/eod_chain.json`; both show `_LKO` suffixes (Lucknow), consistent with each other.
  One of the two (4791536, ticket 269873) still shows location Unknown and no picker/qc - consistent with the
  documented ClickHouse-ingestion-lag caveat for very recent orders, not the join-backwards bug (the other 27/28
  tickets resolve location correctly). 2/28 Unknown, well under the >10% flag threshold.
- Ran `build_full_dataset.py` (2620 tickets; `reconciles` holds: wh_accepted 178 + bod 1726 + considered_bod 499 +
  no_return_record 217 = 2620), `build_report.py`, `build_macro_trend.py` (T-2 cap 2026-11-17), `build_html.py`,
  and the full test suite: `test_wh_comment_classifier.py` 89/89 pass; `test_complaints.py` 1 expected failure
  (the photo-backlog check, see blocker below, not a regression); `node test_view_js.js wfr/damage/swap` all green
  (0 diffs across 7434 + 3717 + 12078 cells).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged, now 13 scheduled runs

Still absent in this fresh container. The Zoho Desk MCP connector is unaffected and was used extensively above
(43-ticket WH-verdict backfill + 1-ticket complaint-baseline gap) - the remaining gap is specifically the REST-only
pipeline scripts not replicated via MCP this run (`pull_dependency.py`, `pull_ticket_routing.py`,
`pull_swap_tickets.py`, `pull_swap_routing.py`), which also need blocker #2 below regardless of credentials.

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged, now 13 scheduled runs

Re-confirmed this run with a direct HTTPS request: `CONNECT tunnel failed, response 403`. Did not re-attempt
`update_environment` - needs a person's approval, nobody is present on this unattended run. This blocks:
- The damage-photo backlog (110 orders now "Photo not read yet" within the last 30 days - up from 94 at the start
  of this run, because the complaint baseline advanced from 2026-11-17 to 2026-11-18 and surfaced more damage
  complaints inside the window; expected consequence of a more current baseline, not a new bug).
- Every RCA/swap image read (receipt/batch photos, courier-label swap evidence) - both tabs stay at 2026-11-03.

## For the owner

Same two asks as prior runs, now compounding for the 13th time:
1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set up itself.
   Order swap and RCA exports are now **16 days stale** (through 2026-11-03).
2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now") fixes the
   photo-read backlog permanently for scheduled runs too. 110 damage-complaint photos from the last 30 days are
   waiting on this right now, growing each run as the complaint baseline catches up.

Both fixes are one-time, few-minute actions in an interactive session.
