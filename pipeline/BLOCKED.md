# Known blockers in this container (2026-11-14 7pm scheduled run)

## 0. THIS RUN (2026-11-14): both connectors worked - core layer refreshed, complaints/damage-photos/swap/RCA still blocked

Checked connectors first per the daily-refresh instructions. Unlike the 2026-11-13 run below, both
required connectors worked this time, confirmed live: `mcp__ClickHouse__get_organizations` /
`get_services_list` resolved org `PlatinumRx` / service `PRx Nucleus` (790ddad5-a6ff-4b03-b135-9292547ed6b6),
and `mcp__Zoho_Desk__searchTickets` returned real tickets (org 60026539570, department Support) on the
first call. So this run did real incremental work on the CORE layer (tabs 1-5), the only layer achievable
without the two blockers in section 1/2 below (re-confirmed this run, not fixed):

- Pulled new Zoho tickets (5 WFR sub-dispositions, createdTimeRange since the last pull) via the Zoho Desk
  MCP, merged 94 new tickets into `zoho_raw90/consolidated.json`.
- Pulled ClickHouse returns/pickers/QC for the 91 new numeric order_ids as `ch_returns_c5.jsonl` /
  `ch_pickers_c5.jsonl` / `ch_qc_c5.jsonl` (incremental chunk, same convention as `c4`), plus cold-chain
  flags (`order_cold_flag.json`, +87 orders) and 3 new picker/QC usernames (`user_names.json`).
- WH-text admission backfill (`wh_text_check.json`): read every comment (via Zoho Desk MCP
  `getTicketComments`, never hand-guessed - classified against the real admission/denial/neutral phrase
  tables) for all 44 new tickets past the 2-day-backlog line (closing the "core WH verdicts read" gate -
  0 unread past T-2) plus 73 of the "stale provisional" no_wh_comment/unrecognized tickets from the last
  14 days (closing 36 of 68; 32 remain for a future run - this was budget-capped, not exhaustive). Found
  one genuine new admission (ticket 268928 / order 4664645, "We have sent short qty to Cx") that had been
  sitting uncached.
- Orders-volume denominators (`orders_by_day.json`, `orders_by_day_location.json`) extended through
  2026-11-13 with the exact query in CLAUDE.md step 4 (JOIN on `order_id`, not `id`).
- `ch_delivered_daily.json` extended through 2026-11-13 (current_status_id=70 query).
- Ran `build_full_dataset.py` (2556 tickets; `reconciles` invariant holds), `build_eod_auto.py` (for_date
  2026-11-12, T-2, 22 tickets, 0 accepted - all denials/no-comment this cycle, so no picker/packer/qc chain
  needed), `build_report.py` (`tab1.reconciles: true`), `build_macro_trend.py` (T-2 cutoff 2026-11-12), and
  `build_html.py`.
- Sanity-checked per CLAUDE.md step 8: `aggregates.json` / `orders_by_day*.json` are dicts (not arrays) and
  non-empty, `order_cold_flag.json` / `user_names.json` / `wh_text_check.json` grew and are non-empty,
  `data_eod.json` location is 9.1% Unknown (under the ~10% backwards-join red flag), no accepted EOD
  tickets this cycle so the picker/packer/qc/manifester chain is correctly all-null.
- Deliberately skipped (optional/lowest priority, pure ClickHouse but no standalone value since the
  Zoho-ticket side of the complaint baseline is REST-blocked regardless): pulling the 4 outstanding
  `cmp_returns_<A>_<B>.json` chunks (`refresh_all.py plan` lists `20261017_20261024` .. `20261107_20261114`).
  `python3 pipeline/refresh_all.py gates` after this run: 10 of 17 green (core data.json, core WH verdicts
  read, EOD tab date = T-2, cmp_wfr_trend/cmp_damage_trend/cmp_summary, warehouse verdict gaps = 0, index.html
  current) - everything achievable without the two structural blockers. Red: core provisional verdicts
  re-read (32 left, see above), returns pull covers through yesterday (skipped, see above), zoho complaint
  tickets / complaints_export.json / order swap export / RCA export / damage photos read (all blocked by
  section 1/2 below, unchanged).

## Blockers unchanged from the 2026-11-13 run (and before), still open

These remain open asks for the owner; this run did not attempt to work around them, per CLAUDE.md
("Do NOT attempt workarounds... report the blocker and stop, a human will resolve it").

### 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - now 8 scheduled runs

Re-confirmed this run: `ls pipeline/.zoho.env` -> No such file. The Zoho Desk MCP connector (used
extensively above, via `searchTickets` + `getTicketComments`) is unaffected - the gap is specifically the
REST-only pipeline scripts (`pull_complaint_tickets.py`, `pull_dependency.py`, `pull_ticket_routing.py`,
`pull_swap_tickets.py`, `recheck_wh_comments.py`'s bulk path), which crash immediately in `zoho_auth.env()`
before any MCP fallback can run. This is why `complaints_export.json` (and everything downstream: order
swap export, RCA export) stays stale at 2026-11-11 / 2026-11-03 - the complaint baseline's Zoho-ticket side
cannot be pulled without it.

### 2. cdn.platinumrx.in not in this environment's network allowlist - re-confirmed this run

Direct `curl` to `https://cdn.platinumrx.in/` this run: `Tunnel connection failed: 403 Forbidden` /
agent-proxy `connect_rejected`. Did not re-attempt `update_environment` to add it - already correctly
refused on multiple prior scheduled runs (needs a person's approval; nobody is present on an unattended
scheduled run). Blocks every damage-photo / RCA-image / swap-image read.

## For the owner

Same two asks as every prior run this week, now compounding (complaints baseline is 3 days stale at the
Zoho-ticket side; order swap / RCA exports are 11 days stale):
1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set up
   itself (a 3-legged OAuth refresh token, not a single API key `request_credential` can inject).
2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now")
   fixes the photo-read backlog permanently for scheduled runs too.
Both fixes are one-time, few-minute actions in an interactive session.

---

# Prior run: 2026-11-13 7pm scheduled run

## 0. THAT RUN: every MCP connector failed to connect - no data pulled, no refresh attempted

Checked connectors first per the daily-refresh instructions, as always. This run, BOTH required
connectors (ClickHouse MCP, Zoho Desk MCP) failed to connect, confirmed on 3 separate `ToolSearch`
attempts a few minutes apart (ruling out a one-off transient blip):
- `ClickHouse`: `CONNECT_TIMEOUT` - "SdkError dialing .../mcp (REQUEST_TIMEOUT)"
- `Zoho_Desk`: `503` - "SdkHttpError dialing .../mcp (CLIENT_HTTP_NOT_IMPLEMENTED)"

Notably, every OTHER configured MCP connector in this container also failed the same way this run
(`Google_Drive` 503, `Vercel` CONNECT_TIMEOUT, `Whimsical` CONNECT_TIMEOUT) - none of them are used
by this pipeline, but their simultaneous failure indicates this is a container/infra-level MCP
connectivity problem tonight, not these two connectors specifically being removed or misconfigured.

**No pipeline step was run.** No ticket pull, no ClickHouse query, no file write, no commit of data
changes - there is nothing to back out since nothing was touched. This is a pure connectivity
failure a human needs to retry/fix (restart the session or its MCP connections); it cannot be
resolved from inside this unattended run. `index.html` and all `pipeline/*.json` files remain exactly
as of the last successful refresh (6bb7d5e, "Refresh 2026-11-12 19:xx IST - 11/14 gates green") -
one day stale, not corrupted or regressed.

## Blockers unchanged from prior runs (2026-11-06 through 2026-11-12, still open, not this run's cause)

These are documented below as-is from the 2026-11-12 run for continuity - they are still open asks
for the owner, but are NOT why this run (2026-11-13) produced nothing; today's run never got past
the connector check, so it never reached the point where these would even apply. Both are
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
