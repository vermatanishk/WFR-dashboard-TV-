# Known blockers in this container (2026-11-10 7pm run)

Both blockers are unchanged from the 2026-11-06 through 2026-11-09 runs - still environment-level, not
data/logic bugs, and still require a person to act (neither can be resolved from inside an unattended
session). This is the **5th consecutive daily run** blocked on the same two items. This run refreshed
everything that doesn't depend on them, and additionally tried (and was refused) a fix for blocker #2:

- Complaint-baseline return pull: pulled the 4 missing ClickHouse chunks for the trailing-28-day
  re-pull window (2026-10-13..2026-11-10) via the ClickHouse MCP, saved as
  `cmp_returns_20261013_20261020.json` / `..._20261020_20261027.json` / `..._20261027_20261103.json` /
  `..._20261103_20261110.json`. `returns pull covers through yesterday` gate is now **green** (was red).
- Rebuilt `complaints_export.json` + the cmp_wfr/cmp_damage/cmp_summary views, `index.html`
  (`build_complaints.py` pass 1 + `cmp_view_spec.py` + `build_html.py` - pass 2 with fresh WH verdicts
  was not run since `recheck_wh_comments.py` needs the missing REST creds, see blocker #1). `core
  data.json` gate stays green (generated 2026-11-09, within the 1-day tolerance - no new core-dataset
  ticket pull attempted this run, to stay lean on token budget; the EOD tab and step-2c backfill were
  also skipped this run for the same reason - neither is gated by `refresh_all.py gates`, and hand-
  editing `build_eod.py`'s TICKETS/WH_COMMENT/ORDER_LOCATION dicts for ~30+ tickets each with full
  Zoho comment-thread reads is the single most expensive manual step in this pipeline).
- `test_complaints.py` (all but the known photo-backlog check), and the JS evaluator (wfr/damage/swap,
  0 differences across 22,698 cells) all pass.
- **Tried to fix blocker #2 this run**: called `update_environment` to add `cdn.platinumrx.in` to the
  Default environment's allowlist. It was refused - "needs a person's approval, and nobody is present
  on this routine run." Confirmed (again) that this cannot be self-served from an unattended scheduled
  run; a person must approve it from an interactive "Run now".
- Did **not** attempt a full `pull_complaint_tickets.py`-equivalent org-wide pull (all dispositions), or
  the RCA/swap pipelines' Dependency/routing/ticket pulls - same reasoning as the last four runs: these
  need hundreds-to-thousands of ticket reads, well past what's reasonable to do by hand through the MCP
  in one lean session. Confirmed `recheck_wh_comments.py` still fails immediately on the missing
  `.zoho.env` (unchanged) rather than attempting a doomed partial run.

`python3 pipeline/refresh_all.py gates` shows 4 red gates, all traceable to the two blockers below (was
5 red gates yesterday - the returns-pull gate is fixed again today after a fresh 28-day re-pull).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged from 2026-11-06 through 09

Still absent in this fresh container (gitignored by design, repo is public). Scripts that call
`zoho_auth.desk_get()` - `pull_complaint_tickets.py`, `recheck_wh_comments.py` (full, uncapped run),
`pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `check_complaints_live.py` -
cannot run (confirmed via `zoho_auth.py`: it needs a persisted 3-legged OAuth client_id/secret/
refresh_token, which is a different kind of credential from what `request_credential` can provision -
that tool injects a single Bearer-style API key per host through the network proxy, not a refresh-token
flow that needs local file persistence). The Zoho Desk MCP connector (available this session, used for
ClickHouse-adjacent read-only lookups) is a documented fallback, but only at bounded scale (dozens of
tickets, not the 2,162-ticket-and-growing org-wide pulls these scripts need for the complaint baseline's
WH-verdict backfill).

`complaints_export.json`'s Zoho-ticket side (`cmp_zoho_tickets.json`) is now **4 days stale** (last
pulled 2026-11-06T06:58:19Z) - past the gate's 1-day tolerance, so `zoho complaint tickets` is red (this
is a separate file from the EOD/core-dataset ticket pulls, which stay current via the MCP when run).
`order swap export` and `RCA export` are stuck at 2026-11-03 for the same reason (their
Dependency/routing/ticket pulls are REST-only) - 7 days stale and growing.

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged from 2026-11-07 through 09

Damage-complaint photo reads (both the Order damage tab and the RCA layer) still need to download images
from `cdn.platinumrx.in`, and this container's network proxy still has no allowlist entry for that host
(confirmed via `get_environment`: network type is "limited", `allowed_hosts` is empty). This run tried
calling `update_environment` directly to add it - refused, because an unattended scheduled run has nobody
present to approve the change. **48 orders** are "Photo not read yet" within the last 30 days now (up
from 32 on 2026-11-09, also reflecting the wider trailing-28-day return-pull window pulled this run) -
the backlog keeps growing.

## For the owner

- Zoho REST: same ask as the last four runs - needs a persistence mechanism (secret storage / env var)
  this session can't set up itself. This is now the limiting factor for 3 of the 4 red gates (complaint
  tickets, order swap, RCA) and the backlog only grows the longer it's missing - complaint tickets are
  now 4 days stale, swap/RCA 7 days stale.
- Network: approving the `cdn.platinumrx.in` allowlist prompt once (next interactive "Run now") fixes
  the photo backlog permanently for future scheduled runs too, since it's a personal-environment-wide
  setting. This run actively tried to propose the change itself (via `update_environment`) and was
  correctly refused since nobody was present to approve it - the fix still needs one interactive
  approval. The backlog is now 48 and still growing - worth prioritizing before it gets much larger.
- Both blockers have now persisted across **5 consecutive scheduled runs** (2026-11-06, 07, 08, 09, 10)
  without anyone acting on them. Flagging this explicitly in case the daily run's commit messages
  aren't being seen - these two fixes are each a one-time, few-minutes action in an interactive session.
