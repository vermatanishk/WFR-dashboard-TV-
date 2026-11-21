# Known blockers in this container (2026-11-21 7pm scheduled run)

## This run: 14/20 gates green via the two working MCP connectors only

Checked connectors first per the daily-refresh instructions: both worked (`mcp__ClickHouse__get_organizations`
resolved org `PlatinumRx` / service `PRx Nucleus`; `mcp__Zoho_Desk__getOrganizations` returned org 60026539570
on the first call, resolving the `USER_NOT_IN_ORG` issue that blocked the 2026-11-20 run earlier that day).
`pipeline/.zoho.env` is still absent and `cdn.platinumrx.in` is still refused by the agent proxy (403 Tunnel
connection failed, re-tested directly with curl) - both unchanged structural blockers, now compounding for many
scheduled runs in a row.

- **Returns-pull coverage**: pulled the 4 due 7-day ClickHouse chunks (`cmp_returns_20261024_20261031` through
  `..._20261114_20261121`) via the ClickHouse MCP, exact query from `build_complaints.py`'s docstring. Coverage
  closed: 2026-08-26..2026-11-21.
- **Core WH-verdict backfill (gate-exact)**: 20 tickets past T-2 with no cached verdict, computed from the exact
  `refresh_all.py` gates() logic. Resolved all 20 via the Zoho Desk MCP (`searchTickets` by `ticketNumber` - each
  call individually, never batched-and-paired-by-position; `getTicketComments` per ticket, full thread read before
  classifying), classified with the real `classify_wh_comments()` (imported, not hand-guessed): 2 admissions
  (270206 "we have sent wrong sku to CX"; 270208 "we have sent short qty to CX"), 11 denials (stock template "We
  have sent proper medicine to CX"), 7 `no_wh_comment` (no Warehouse-role comment anywhere in the thread - L2-only
  or ticket-dependency notes). Both core WH-verdict gates closed.
- **Zoho complaint-ticket pull (REST blocked)**: `pull_complaint_tickets.py` needs `pipeline/.zoho.env` and fails
  immediately. Replicated it via the Zoho Desk MCP for the 4 days it needed (2026-11-18 through 21, the "last 3
  days + the day already 3 days old" window): `searchTickets` with an explicit lean `fields` list (ticketNumber,
  createdTime, status, channel, cf_order_id, cf_dispositions, cf_sub_disposition, cf_dependency) to avoid pulling
  full descriptions/contact PII into context, paginated 100/page by exact count (188, 145, 161, 147 tickets).
  Wrote the same `cmp_zoho_tickets.json` schema `pull_complaint_tickets.py` would have.
- **Complaint-baseline WH-verdict gap**: after rebuilding `build_complaints.py`, 6 ticketed complaints past T-2 had
  no cached verdict (270217, 270268, 270215, 270292, 270235, 270171) - read live via the MCP, 1 denial (270292,
  "We have sent proper medicine to CX"), 5 `no_wh_comment` (no Warehouse-role comment in any of those threads).
  Gap closed (0). Re-ran `build_complaints.py` (pass 2) and `cmp_view_spec.py`.
- **EOD tab**: `build_eod_auto.py` for_date 2026-11-19 (20 tickets, 2 accepted - same two admissions above, orders
  4823554/4798417). Packer/manifester for both pulled via the ClickHouse MCP (`marketplace_order_status_log`,
  status 52/64) into `zoho_raw90/eod_chain.json`; picker cross-checked via `warehouse_warehouse_scan_log` max-picks.
  Both orders resolve location correctly (Lucknow / Mumbai, consistent with their picker/packer usernames).
- Ran `build_full_dataset.py` (2680 tickets; `reconciles` holds: wh_accepted 184 + bod 1739 + considered_bod 530 +
  no_return_record 227 = 2680), `build_report.py`, `build_macro_trend.py` (T-2 cap 2026-11-19), `archive_exports.py`
  (append-only, nothing shrank), `build_html.py`, and the full test suite: `test_wh_comment_classifier.py` 99/99
  pass; `test_complaints.py` 1 expected failure (the photo-backlog check, see blocker below, not a regression);
  `node test_view_js.js wfr/damage/swap` all green (0 diffs across 7434 + 3717 + 12078 cells); `node
  test_gsheet_upsert.js` 9/9 pass.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`)

Still absent in this fresh container. The Zoho Desk MCP connector is unaffected and was used extensively above
(20-ticket core WH-verdict backfill + 6-ticket complaint-baseline gap + the 4-day Zoho ticket pull itself, all via
MCP) - the remaining gap is specifically the REST-only pipeline scripts not replicated via MCP this run
(`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `pull_swap_routing.py`), which also need
blocker #2 below regardless of credentials, since both swap and RCA need image evidence.

## 2. cdn.platinumrx.in not in this environment's network allowlist

Re-confirmed this run with a direct curl request: `CONNECT tunnel failed, response 403`. Did not re-attempt
`update_environment` - needs a person's approval, nobody is present on this unattended run. This blocks:
- The damage-photo backlog within the 60-day gate window: 11 orders from 2026-11-20 are "Photo not read yet"
  (confirmed via the ClickHouse MCP that return-item image URLs exist for all 11 - the data pull itself is fine,
  only the image *download* is blocked). Everything through 2026-11-19 was already read by prior runs.
- Every RCA/swap image read (receipt/batch photos, courier-label swap evidence) - both tabs stay at 2026-11-03.

## For the owner

Same two asks as prior runs, now well past two weeks of compounding:
1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set up itself.
   Order swap and RCA exports are now **18 days stale** (through 2026-11-03).
2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now") fixes the
   photo-read backlog permanently for scheduled runs too - only 11 photos are waiting on this right now (small
   because the complaint baseline is otherwise current), but it compounds every day this stays unapproved, and it
   is the same blocker stopping all RCA/swap image evidence.

Both fixes are one-time, few-minute actions in an interactive session.
