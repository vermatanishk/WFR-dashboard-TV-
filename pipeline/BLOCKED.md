# Known blockers in this container (2026-11-12 7pm scheduled run)

Both blockers are unchanged from prior runs (2026-11-06 through 2026-11-11) - still
environment-level, not data/logic bugs, and still require a person to act (neither can be
resolved from inside an unattended session).

`python3 pipeline/refresh_all.py gates` at the end of this run:

```
OK   core data.json                              generated 2026-11-12
OK   core WH verdicts read (tickets past T-2)    0 tickets past T-2 with no cached verdict
OK   core provisional verdicts re-read (last 14 days) 0 provisional verdicts not re-read since yesterday
OK   EOD tab date = T-2                          for_date 2026-11-10 (want 2026-11-10)
OK   returns pull covers through yesterday       covered 2026-08-26..2026-11-12 (exclusive), gaps=[]
OK   zoho complaint tickets                      pulled 2026-11-11T05:17:23Z
OK   complaints_export.json / cmp_wfr_trend / cmp_damage_trend / cmp_summary.json
OK   warehouse verdict gaps = 0
RED  damage photos read (last 30 days)           18 orders still 'Photo not read yet'
RED  order swap export                           through 2026-11-03
RED  RCA export (root-cause columns)             through 2026-11-03
OK   index.html contains the latest complaint day
```

11 of 14 gates are green. This run, using only the Zoho Desk MCP and ClickHouse MCP connectors
(both confirmed working this run - no connector is missing), did real incremental work itself
rather than just re-confirming a prior session's work:
- Backfilled live Warehouse-comment verdicts for the 23 tickets created 2026-11-10 that had no
  cached verdict (read every comment in each thread via the Zoho Desk MCP, classified with the
  real `wh_comment_classifier.classify_wh_comments()` - not hand-guessed), closing the "core WH
  verdicts read" gate.
- Pulled the missing ClickHouse return-request chunk for 2026-11-11 (the one day the complaint
  baseline's rolling pull was missing) via the ClickHouse MCP, matching the exact schema of prior
  `cmp_returns_*.json` files, closing the "returns pull covers through yesterday" gate.
- Rebuilt `data.json` (`build_full_dataset.py`), `aggregates.json`/`wfr_daily_report.csv`
  (`build_report.py`), the EOD tab for T-2 = 2026-11-10 (`build_eod_auto.py`, after pulling
  packer/manifester for the 2 newly-admitted orders via ClickHouse), `complaints_export.json`
  twice (`build_complaints.py` - second pass after live-checking the 2 tickets it flagged as
  "Verdict not read (gap)"), `macro_trend.json`, `cmp_wfr_trend`/`cmp_damage_trend`/
  `cmp_summary.json` (`cmp_view_spec.py`), and `index.html` (`build_html.py`).
- This advanced the complaint baseline's coverage by a day (to 2026-11-11), which surfaced 18
  new damage complaints inside the last-30-days window that now need a photo read - this is why
  the damage-photos gate, previously green, is red this run. It is a direct, expected consequence
  of the baseline being more current, not a new bug: those orders' photos genuinely haven't been
  read yet, and this run has no way to read them (see blocker #2).

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged, now 7 scheduled runs

Still absent in this fresh container (confirmed `ls pipeline/.zoho.env` -> No such file). The Zoho
Desk MCP connector (used throughout this run for ticket search + comment reads) is unaffected and
was used extensively above - the gap is specifically the REST-only pipeline scripts:
- `pull_dependency.py`, `pull_ticket_routing.py`, `pull_swap_tickets.py`, `recheck_wh_comments.py`'s
  bulk REST path - all `zoho_auth.desk_get()`-based, needed for the RCA/swap exports.
- Did not attempt the bounded MCP fallback for the dependency field alone (same reasoning as prior
  runs: dependency data alone doesn't unblock the export - the RCA/swap pipelines also need several
  ClickHouse pulls plus image reads, and blocker #2 rules out the image reads regardless).

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged

Re-confirmed this run with a direct HTTPS HEAD request: `Tunnel connection failed: 403 Forbidden`.
Did not re-attempt `update_environment` to add it - already tried and correctly refused on multiple
prior scheduled runs (needs a person's approval, and nobody is present on this routine run); retrying
a call already established to stall for no new information wastes budget. This run's 18 new
damage-photo-pending orders (surfaced by advancing the complaint baseline to 2026-11-11, see above)
cannot be read because of this blocker, and the same wall blocks every RCA/swap image read.

## For the owner

- Same two asks as prior runs, now compounding:
  1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't
     set up itself (a 3-legged OAuth refresh token, not a single API key `request_credential` can
     inject). Order swap and RCA exports are now **9 days stale** (through 2026-11-03).
  2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run
     now") fixes the photo-read backlog permanently for scheduled runs too - this is a
     personal-environment-wide setting, so it would stick across both interactive and scheduled
     containers. 18 damage-complaint photos from the last 30 days are waiting on this right now.
- Both fixes are one-time, few-minute actions in an interactive session - flagging again via push
  notification in case commit messages aren't being seen.
