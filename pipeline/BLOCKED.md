# Known blockers in this container (2026-11-09 7pm run)

Both blockers are unchanged from the 2026-11-06 through 2026-11-08 runs - still environment-level, not
data/logic bugs, and still require a person to act (neither can be resolved from inside an unattended
session). This is the 4th consecutive daily run blocked on the same two items. This run refreshed
everything that doesn't depend on them:

- Core 90-day dataset: incremental ClickHouse return-request pull for the complaint baseline (4 missing
  7-day chunks, 2026-10-12..2026-11-09) - `returns pull covers through yesterday` gate is now green
  (was red for 3 days). `core data.json` gate is green (regenerated today).
- EOD tab: for_date 2026-11-07, 32 T-2 tickets pulled and classified via Zoho Desk MCP
  (`searchTickets` + `getTicketComments`, full comment threads enumerated before classifying -
  2 genuine WH admissions, both "wrong sku"), full fulfilment-chain attribution for both WH-Accepted
  tickets, 0% Unknown location. All 32 verdicts synced into `wh_text_check.json` (none pre-existing).
  `warehouse verdict gaps = 0` gate is green.
- Step 2c (considered_bod text-admission backfill): 0 new tickets were eligible this run (every
  ticket >=2 days old with a return record already has a cached verdict from prior backfills).
- Rebuilt `data.json`/`aggregates.json`/`personnel.json`/`trend.json`/`macro_trend.json`, the
  complaint baseline (`complaints_export.json` + cmp_wfr/cmp_damage/cmp_summary views) from the fresh
  return pull, `index.html`. `test_complaints.py` (all but the known photo-backlog check),
  `test_wh_comment_classifier.py` (89/89), and the JS evaluator (wfr/damage/swap, 0 differences) all
  pass.
- Did **not** attempt a full `pull_complaint_tickets.py`-equivalent org-wide pull (all dispositions),
  or the RCA/swap pipelines' Dependency/routing/ticket pulls - same reasoning as the last three runs:
  these need hundreds-to-thousands of ticket reads, well past what's reasonable to do by hand through
  the MCP in one session. Confirmed `recheck_wh_comments.py` still fails immediately on the missing
  `.zoho.env` (see below) rather than attempting a doomed partial run.

`python3 pipeline/refresh_all.py gates` shows 4 red gates, all traceable to the two blockers below (was
5 red gates yesterday - the returns-pull gate is fixed).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged from 2026-11-06 through 08

Still absent in this fresh container (gitignored by design, repo is public). Scripts that call
`zoho_auth.desk_get()` - `pull_complaint_tickets.py`, `recheck_wh_comments.py` (full, uncapped run),
`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `check_complaints_live.py` -
cannot run; confirmed again this run (`recheck_wh_comments.py` fails with `FileNotFoundError` on
`pipeline/.zoho.env` before making any network call). The Zoho Desk MCP connector (available this
session) is a documented fallback, but only at bounded scale (dozens of tickets, not the
2,162-ticket-and-growing org-wide pulls these scripts need for the complaint baseline's WH-verdict
backfill).

`complaints_export.json`'s Zoho-ticket side (`cmp_zoho_tickets.json`) is now **3 days stale** (last
pulled 2026-11-06T06:58:19Z) - past the gate's 1-day tolerance, so `zoho complaint tickets` is red (this
is a separate file from the EOD/core-dataset ticket pulls, which stay current via the MCP).
`order swap export` and `RCA export` are stuck at 2026-11-03 for the same reason (their
Dependency/routing/ticket pulls are REST-only) - 6 days stale and growing.

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged from 2026-11-07/08

Damage-complaint photo reads (both the Order damage tab and the RCA layer) still need to download images
from `cdn.platinumrx.in`, and this container's network proxy still has no allowlist entry for that host
(confirmed via `get_environment`: network type is "limited", `allowed_hosts` is empty). Adding it needs a
person to approve an `update_environment` prompt, and this is an unattended scheduled run with nobody
present to answer it, so this run did not propose one (same reasoning as 2026-11-07/08 - repeating the
proposal from an unattended run each day is not useful; it genuinely needs a person in an interactive
session). **32 orders** are "Photo not read yet" within the last 30 days now (up from 27 on
2026-11-08) - the backlog keeps growing by ~1-5/day.

## For the owner

- Zoho REST: same ask as the last three runs - needs a persistence mechanism (secret storage / env var)
  this session can't set up itself. This is now the limiting factor for 3 of the 4 red gates (complaint
  tickets, order swap, RCA) and the backlog only grows the longer it's missing - complaint tickets are
  now 3 days stale, swap/RCA 6 days stale.
- Network: approving the `cdn.platinumrx.in` allowlist prompt once (next interactive "Run now") fixes
  the photo backlog permanently for future scheduled runs too, since it's a personal-environment-wide
  setting. The backlog is now 32 and still growing - worth prioritizing before it gets much larger.
- Both blockers have now persisted across 4 consecutive scheduled runs (2026-11-06, 07, 08, 09) without
  anyone acting on them. Flagging this explicitly in case the daily run's commit messages aren't being
  seen - these two fixes are each a one-time, few-minutes action in an interactive session.
