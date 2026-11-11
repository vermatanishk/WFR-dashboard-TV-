# Known blockers in this container (2026-11-11 7pm scheduled run)

Both blockers are unchanged from 2026-11-06 through 2026-11-10 - still environment-level, not data/logic
bugs, and still require a person to act (neither can be resolved from inside an unattended session).
This is the **6th consecutive scheduled 7pm run** blocked on blocker #1 below; blocker #2
(cdn.platinumrx.in) did not affect this run's gates (see note).

`python3 pipeline/refresh_all.py gates` at the start of this run (13:43 UTC / 19:13 IST):

```
OK   core data.json                              generated 2026-11-11
OK   core WH verdicts read (tickets past T-2)    0 tickets past T-2 with no cached verdict
OK   core provisional verdicts re-read (last 14 days) 0 provisional verdicts not re-read since yesterday
OK   EOD tab date = T-2                          for_date 2026-11-09 (want 2026-11-09)
OK   returns pull covers through yesterday       covered 2026-08-26..2026-11-11 (exclusive), gaps=[]
OK   zoho complaint tickets                      pulled 2026-11-11T05:17:23Z
OK   complaints_export.json / cmp_wfr_trend / cmp_damage_trend / cmp_summary.json
OK   warehouse verdict gaps = 0
OK   damage photos read (last 30 days)            0 orders still 'Photo not read yet'
RED  order swap export                           through 2026-11-03
RED  RCA export (root-cause columns)              through 2026-11-03
OK   index.html contains the latest complaint day
```

9 of 11 gates are green. Everything that's green was refreshed by an **interactive owner session earlier
today** (commits `f12abac` / `4d32b6b`, 2026-11-11 10:4x IST) which evidently had working Zoho REST
creds and/or cdn access that this scheduled 7pm container does not have - this run did not need to redo
that work, confirmed it's still within tolerance, and made no changes to it (kept this run lean, per the
token-budget instruction). This run did not re-pull ClickHouse/Zoho data for `data.json`/EOD/complaints
beyond what the gates already confirm fresh, since none of today's 9 green gates needed it and doing so
would have duplicated this morning's refresh for a daily job explicitly meant to run once.

## 1. Zoho Desk REST credentials missing (`pipeline/.zoho.env`) - unchanged, now 6 scheduled runs

Still absent in this fresh container (confirmed `ls pipeline/.zoho.env` -> No such file). This is the
sole blocker on both red gates:
- `order swap export` / `RCA export` need `pull_dependency.py`, `pull_ticket_routing.py`,
  `pull_swap_tickets.py` (all REST-only, `zoho_auth.desk_get()`).
- Checked the bounded MCP fallback for just the dependency field (CLAUDE.md's documented fallback,
  `searchTickets` by ticketNumber -> `cf.cf_dependency`): 143 tickets created since 2026-11-03 are
  missing from `ticket_dependency.json`, which is within the fallback's usual bounded scale. **Did not
  run it**, because dependency data alone doesn't unblock the export - the RCA/swap pipelines also need
  several more ClickHouse pulls (return outcomes, missing-item lines, wrong-medicine raw, order meta,
  swap routing/status) and, critically, **image reads for every new RCA/damage-relevant order**, which
  blocker #2 below rules out entirely in this container regardless of REST access. Doing the
  dependency-only piece without the rest would leave the export incomplete and still red, for a real
  token cost - not a good trade for a lean daily run that's explicitly meant to skip exactly this kind of
  partial, doomed-to-stay-red work (same reasoning as the last 5 runs).

## 2. cdn.platinumrx.in not in this environment's network allowlist - unchanged

Re-confirmed via `get_environment` this run: network type "limited", `allowed_hosts: []` (still empty).
Did not re-attempt `update_environment` to add it - already tried and correctly refused on four separate
prior scheduled runs ("needs a person's approval, and nobody is present on this routine run"); retrying a
call already established to fail wastes budget for no new information. This run's `damage photos read`
gate reads green only because no new damage-photo backlog has accumulated since this morning's
owner-assisted refresh (8.5 hours), not because this blocker was fixed - any new damage complaints
between now and the next run that need a photo read will still hit this wall.

## For the owner

- Same two asks as the last 5 runs, now compounding:
  1. **Zoho REST**: `pipeline/.zoho.env` needs a persistence mechanism this unattended session can't set
     up itself (a 3-legged OAuth refresh token, not a single API key `request_credential` can inject).
     This morning's interactive session apparently had it; the 7pm scheduled container does not. Order
     swap and RCA exports are now **8 days stale** (through 2026-11-03) and the gap only grows while
     every *scheduled* run hits this wall, even on days an interactive session fixes everything else.
  2. **Network**: approving the `cdn.platinumrx.in` allowlist prompt once (from an interactive "Run now")
     fixes the photo-read backlog permanently for scheduled runs too - this is a personal-environment-
     wide setting, so it would stick across both interactive and scheduled containers.
- This is the **6th consecutive scheduled 7pm run** flagging blocker #1 (2026-11-06 through 2026-11-11)
  without it being resolved for the scheduled container specifically. Both fixes are one-time, few-minute
  actions in an interactive session - flagging again via push notification in case commit messages
  aren't being seen.
