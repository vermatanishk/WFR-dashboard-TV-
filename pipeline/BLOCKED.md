# Known blockers in this container (2026-11-08 7pm run)

Both blockers are unchanged from the 2026-11-06 and 2026-11-07 runs - still environment-level, not
data/logic bugs, and still require a person to act (neither can be resolved from inside an unattended
session). This run refreshed everything that doesn't depend on them: core 90-day dataset (ticket pull,
ClickHouse joins, cold-chain, personnel), EOD tab (for_date 2026-11-06, 37 tickets, 2 WH-accepted text,
full fulfilment-chain attribution for both), orders-volume denominators, RFD weekly (today is Sunday -
full week 2026-11-02..2026-11-08 recomputed), and the complaint-baseline's ClickHouse return side (today
being Sunday, the full 60-day window was re-pulled in 9 chunks - `returns pull covers through yesterday`
gate is now green, `WH verdict gaps = 0`). `python3 pipeline/refresh_all.py gates` shows 4 red gates, all
traceable to the two blockers below.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged from 2026-11-06/07

Still absent in this fresh container (gitignored by design, repo is public). Scripts that call
`zoho_auth.desk_get()` - `pull_complaint_tickets.py`, `recheck_wh_comments.py` (full, uncapped run),
`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `check_complaints_live.py` -
cannot run. The Zoho Desk MCP connector (available this session) is a documented fallback, but only
at bounded scale (dozens of tickets, not the full org-wide pulls these scripts do).

This run used the MCP fallback at bounded scale where it mattered:
- Main 90-day dataset: pulled new mis-shipment tickets (Nov 7-8) via `searchTickets` per sub-disposition
  (19 new, merged into `consolidated.json`) - this step has always used the MCP directly, not REST, so
  it is unaffected by the credential gap.
- EOD tab: resolved internal ids and read full comment threads for all 37 T-2 (2026-11-06) tickets via
  `searchTickets`/`getTicketComments`; synced into `wh_text_check.json`.
- Step 2c (considered_bod text-admission backfill): checked - 0 tickets were eligible this run (every
  ticket >=2 days old with a return record already has a cached verdict from prior backfills).
- Did **not** attempt a full `pull_complaint_tickets.py`-equivalent org-wide pull (all dispositions, not
  just the 5 mis-shipment ones), or the RCA/swap pipelines' Dependency/routing/ticket pulls - same
  reasoning as the last two runs: these need hundreds-to-thousands of ticket reads, well past what's
  reasonable to do by hand through the MCP in one session.

`complaints_export.json`'s Zoho-ticket side (`cmp_zoho_tickets.json`) is now **2 days stale** (last
pulled 2026-11-06T06:58:19Z) - past the gate's 1-day tolerance, so `zoho complaint tickets` is red. The
ClickHouse return side is fully current (through 2026-11-07). `order swap export` and `RCA export` are
stuck at 2026-11-03 for the same reason (their Dependency/routing/ticket pulls are REST-only).

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged from 2026-11-07

Damage-complaint photo reads (both the Order damage tab and the RCA layer) still need to download images
from `cdn.platinumrx.in`, and this container's network proxy still returns 403 for that host (confirmed
again this run with a direct curl check). Adding it needs a person to approve an `update_environment`
prompt, and this is an unattended scheduled run with nobody present to answer it. **27 orders** are
"Photo not read yet" within the last 30 days now (up from 13 on 2026-11-07 - the backlog is growing
because today's full return-pull surfaced more damage orders); `test_complaints.py`'s photo-backlog
check was run with `PHOTO_BACKLOG_OK=1` to allow this interim push - `refresh_all.py gates` still
correctly reports it red.

## For the owner

- Zoho REST: same ask as the last two runs - needs a persistence mechanism (secret storage / env var)
  this session can't set up itself. This is now the limiting factor for 3 of the 4 red gates (complaint
  tickets, order swap, RCA) and the backlog only grows the longer it's missing.
- Network: approving the `cdn.platinumrx.in` allowlist prompt once (next interactive "Run now") fixes
  the photo backlog permanently for future scheduled runs too, since it's a personal-environment-wide
  setting. The backlog is now 27 and growing ~2/day - worth prioritizing before it gets much larger.
